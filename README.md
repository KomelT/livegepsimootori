[![CircleCI](https://dl.circleci.com/status-badge/img/gh/routechoiceslivegps/livegepsimootori/tree/main.svg?style=svg)](https://dl.circleci.com/status-badge/redirect/gh/routechoiceslivegps/livegepsimootori/tree/main) [![pre-commit.ci status](https://results.pre-commit.ci/badge/github/routechoiceslivegps/livegepsimootori/main.svg)](https://results.pre-commit.ci/latest/github/routechoiceslivegps/livegepsimootori/main) [![codecov](https://codecov.io/gh/routechoiceslivegps/livegepsimootori/graph/badge.svg?token=OZLCAY280V)](https://codecov.io/gh/routechoiceslivegps/livegepsimootori)


Routechoices server
===================

Code for the server of the "Routechoices — Live GPS Tracking" platform.

It includes:

  - The site static content.
  - A frontend server for listing and displaying live and archived events.
  - A dashboard for users to manage their events, maps, devices...
  - A REST API and its documentation.
  - A TCP server for listening to dedicated GPS trackers.
  - A WMS server for serving events maps.
  - A Tile server for serving background layers tiles.
  - An admin interface for the staff.

This project heavily rely on the Django and the Tornado Web python frameworks.

Hosted at https://www.routechoices.com

```
docker build -t rphlo/routechoices-dev-server:latest -f docker/django.dockerfile .

./dc up -d
./da migrate
./da collectstatic --noinput
./da compress --force


./dc exec django
python - <<'PY'
from django.contrib.sites.models import Site
s = Site.objects.get_current()
s.domain = "track.meshtrail.si"
s.name = "track.meshtrail.si"
s.save()
print("Updated site:", s.domain)
PY
```