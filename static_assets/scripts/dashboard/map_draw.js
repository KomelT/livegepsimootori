(() => {
	const map = L.map("map", { tap: false }).setView([0, 0], 2);
	// geocoder (map search)
	const geocoder = L.Control.geocoder({
		defaultMarkGeocode: false,
	});
	geocoder.on("markgeocode", (e) => {
		map.fitBounds(e.geocode.bbox);
	});
	geocoder.addTo(map);

	// maps layer
	const baseLayers = getBaseLayers();
	const defaultLayer = baseLayers["Open Street Map"];
	map.addLayer(defaultLayer);
	const controlLayers = L.control.layers(baseLayers);
	map.addControl(controlLayers);
	if (L.Browser.touch && L.Browser.mobile) {
		map.on("baselayerchange", (e) => {
			controlLayers.collapse();
		});
	}
	// Draw on map
	const drawnItems = new L.FeatureGroup();
	u("#submit-btn").attr({ disabled: true });
	map.addLayer(drawnItems);
	const drawControl = new L.Control.Draw({
		draw: {
			polyline: {
				metric: true,
				feet: false,
				showLength: false,
				shapeOptions: { color: "#f52fe4" },
			},
			polygon: false,
			rectangle: false,
			circle: false,
			marker: false,
			circlemarker: { color: "#f52fe4", fill: false },
		},
		edit: {
			featureGroup: drawnItems,
		},
	});
	map.addControl(drawControl);

	map.on(L.Draw.Event.CREATED, (e) => {
		drawnItems.addLayer(e.layer);
		u("#submit-btn").attr({ disabled: false });
		setGPX();
	});

	map.on(L.Draw.Event.EDITED, (e) => {
		setGPX();
	});

	map.on(L.Draw.Event.DELETED, (e) => {
		const layers = e.layers;
		layers.eachLayer((layer) => {
			drawnItems.removeLayer(layer);
		});
		if (drawnItems.getLayers().length === 0) {
			u("#submit-btn").attr({ disabled: true });
		} else {
			setGPX();
		}
	});

	const setGPX = () => {
		const lines = [];
		const wpts = [];
		drawnItems.eachLayer((layer) => {
			if (layer instanceof L.Polyline) {
				lines.push(layer.getLatLngs());
			} else {
				wpts.push(layer.getLatLng());
			}
		});
		let result =
			'<?xml version="1.0" encoding="UTF-8"?><gpx xmlns="http://www.topografix.com/GPX/1/1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://www.topografix.com/GPX/1/1 http://www.topografix.com/GPX/1/1/gpx.xsd" version="1.1" creator="track.meshtrail.si">';
		result += lines.reduce((accum, curr) => {
			let segmentTag = "<trk><trkseg>";
			segmentTag += curr
				.map((point) => `<trkpt lat="${point.lat}" lon="${point.lng}"></trkpt>`)
				.join("");
			segmentTag += "</trkseg></trk>";
			const accumOut = accum + segmentTag;
			return accumOut;
		}, "");
		result += wpts.reduce((accum, point) => {
			const wptTag = `<wpt lat="${point.lat}" lon="${point.lng}"></wpt>`;
			const accumOut = accum + wptTag;
			return accumOut;
		}, "");
		result += "</gpx>";
		const file = new File(
			[result],
			`Drawn map ${dayjs().local().format("YYYY-MM-DD HH:mm:ss")}.gpx`,
			{ type: "application/xml", lastModified: new Date().getTime() },
		);
		const container = new DataTransfer();
		container.items.add(file);
		u("#id_gpx_file").first().files = container.files;
	};

	// Center on load
	fetch(`${window.local.apiRoot}check-latlon`)
		.then((r) => r.json())
		.then((data) => {
			if (data.status === "success") {
				map.setView([data.lat, data.lon], 10, {
					duration: 0,
				});
			}
		})
		.catch();
})();
