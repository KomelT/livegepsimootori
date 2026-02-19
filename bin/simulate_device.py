#!/usr/bin/env python3
"""
Simulate a device posting location data to the Routechoices API.
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
from dataclasses import dataclass
from typing import Iterable, List, Tuple

import requests
from xml.etree import ElementTree as ET

EARTH_METERS_PER_DEG = 111_111.0


@dataclass
class Point:
    ts: int
    lat: float
    lon: float


def build_base_url(args: argparse.Namespace) -> str:
    if args.base_url:
        return args.base_url.rstrip("/")
    parent_host = args.parent_host or os.environ.get("PARENT_HOST")
    if not parent_host:
        raise SystemExit(
            "Missing base URL. Provide --base-url or set PARENT_HOST env var."
        )
    return f"https://api.{parent_host}"


def meters_to_deg_lat(meters: float) -> float:
    return meters / EARTH_METERS_PER_DEG


def meters_to_deg_lon(meters: float, lat: float) -> float:
    return meters / (EARTH_METERS_PER_DEG * math.cos(math.radians(lat)))


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(a))


def parse_gpx_points(path: str) -> List[Tuple[float, float]]:
    tree = ET.parse(path)
    root = tree.getroot()
    points: List[Tuple[float, float]] = []
    # GPX uses namespaces; match by localname to avoid hardcoding
    for elem in root.iter():
        tag = elem.tag
        if tag.endswith("trkpt") or tag.endswith("rtept"):
            lat = elem.attrib.get("lat")
            lon = elem.attrib.get("lon")
            if lat is None or lon is None:
                continue
            points.append((float(lat), float(lon)))
    if len(points) < 2:
        raise SystemExit("GPX must contain at least 2 points")
    return points


def gpx_points_to_sim(points: List[Tuple[float, float]], speed_kmh: float) -> List[Point]:
    if speed_kmh <= 0:
        raise SystemExit("--speed-kmh must be > 0")
    speed_mps = speed_kmh / 3.6
    start_ts = int(time.time())
    sim: List[Point] = []
    ts = start_ts
    prev_lat, prev_lon = points[0]
    sim.append(Point(ts, prev_lat, prev_lon))
    for lat, lon in points[1:]:
        dist = haversine_m(prev_lat, prev_lon, lat, lon)
        dt = max(1, int(round(dist / speed_mps)))
        ts += dt
        sim.append(Point(ts, lat, lon))
        prev_lat, prev_lon = lat, lon
    return sim


def gen_circle_points(
    start_lat: float,
    start_lon: float,
    radius_m: float,
    step: int,
    start_ts: int,
    interval_s: int,
) -> Point:
    angle = (step % 360) * math.pi / 180.0
    d_lat = meters_to_deg_lat(radius_m * math.sin(angle))
    d_lon = meters_to_deg_lon(radius_m * math.cos(angle), start_lat)
    return Point(start_ts + step * interval_s, start_lat + d_lat, start_lon + d_lon)


def gen_line_points(
    start_lat: float,
    start_lon: float,
    step_m: float,
    step: int,
    start_ts: int,
    interval_s: int,
    bearing_deg: float,
) -> Point:
    angle = math.radians(bearing_deg)
    d_lat = meters_to_deg_lat(step_m * step * math.cos(angle))
    d_lon = meters_to_deg_lon(step_m * step * math.sin(angle), start_lat)
    return Point(start_ts + step * interval_s, start_lat + d_lat, start_lon + d_lon)


def gen_random_walk_points(
    prev: Point,
    step_m: float,
    interval_s: int,
) -> Point:
    angle = random.random() * 2 * math.pi
    d_lat = meters_to_deg_lat(step_m * math.cos(angle))
    d_lon = meters_to_deg_lon(step_m * math.sin(angle), prev.lat)
    return Point(prev.ts + interval_s, prev.lat + d_lat, prev.lon + d_lon)


def iter_points(args: argparse.Namespace) -> Iterable[Point]:
    if args.gpx:
        pts = parse_gpx_points(args.gpx)
        yield from gpx_points_to_sim(pts, args.speed_kmh)
        return

    start_ts = int(time.time())
    if args.pattern == "circle":
        for step in range(args.count):
            yield gen_circle_points(
                args.start_lat,
                args.start_lon,
                args.radius_m,
                step,
                start_ts,
                args.interval,
            )
    elif args.pattern == "line":
        for step in range(args.count):
            yield gen_line_points(
                args.start_lat,
                args.start_lon,
                args.step_m,
                step,
                start_ts,
                args.interval,
                args.bearing_deg,
            )
    else:
        prev = Point(start_ts, args.start_lat, args.start_lon)
        for _ in range(args.count):
            prev = gen_random_walk_points(prev, args.step_m, args.interval)
            yield prev


def post_batch(
    session: requests.Session,
    url: str,
    device_id: str,
    secret: str | None,
    battery: int | None,
    points: List[Point],
    timeout: int,
) -> None:
    data = {
        "device_id": device_id,
        "latitudes": ",".join(f"{p.lat:.6f}" for p in points),
        "longitudes": ",".join(f"{p.lon:.6f}" for p in points),
        "timestamps": ",".join(str(p.ts) for p in points),
    }
    if secret:
        data["secret"] = secret
    if battery is not None:
        data["battery"] = str(battery)
    res = session.post(url, data=data, timeout=timeout)
    if not (200 <= res.status_code < 300):
        raise RuntimeError(f"POST failed: {res.status_code} {res.text}")


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Simulate a tracker device")
    p.add_argument("--device-id", required=True)
    p.add_argument("--secret")
    p.add_argument("--base-url")
    p.add_argument("--parent-host")
    p.add_argument("--interval", type=int, default=5, help="seconds between points")
    p.add_argument("--count", type=int, default=60, help="number of points")
    p.add_argument("--batch-size", type=int, default=1, help="points per POST")
    p.add_argument("--timeout", type=int, default=10)
    p.add_argument("--battery", type=int, default=None)
    p.add_argument("--pattern", choices=["circle", "random", "line"], default="circle")
    p.add_argument("--start-lat", type=float, default=60.1699)
    p.add_argument("--start-lon", type=float, default=24.9384)
    p.add_argument("--radius-m", type=float, default=30.0)
    p.add_argument("--step-m", type=float, default=5.0)
    p.add_argument("--bearing-deg", type=float, default=90.0)
    p.add_argument("--gpx", help="Path to GPX file to simulate")
    p.add_argument("--speed-kmh", type=float, default=6.0, help="Used with --gpx")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    if args.device_id.isdigit() and not args.secret:
        print(
            "Warning: numeric device_id requires a valid secret or superuser auth; "
            "request may be rejected.",
            file=sys.stderr,
        )

    base_url = build_base_url(args)
    url = f"{base_url}/locations"

    session = requests.Session()
    points_buf: List[Point] = []

    prev_ts = None
    for idx, point in enumerate(iter_points(args), start=1):
        if prev_ts is not None:
            delay = max(0, point.ts - prev_ts)
            if delay:
                time.sleep(delay)
        points_buf.append(point)
        if len(points_buf) >= args.batch_size:
            post_batch(
                session,
                url,
                args.device_id,
                args.secret,
                args.battery,
                points_buf,
                args.timeout,
            )
            points_buf.clear()
        prev_ts = point.ts

    if points_buf:
        post_batch(
            session,
            url,
            args.device_id,
            args.secret,
            args.battery,
            points_buf,
            args.timeout,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
