# Data sources of the drone courier episode

| data | source | where | terms |
|---|---|---|---|
| hourly wind at 10 and 100 m, gusts at 10 m, temperature at 2 m, 10 days of 2025 per city | ERA5 hourly reanalysis, Copernicus Climate Change Service (C3S), fetched through the Open-Meteo Historical Weather API (`models=era5`, 0.25° cell) | `world/<city>.json` (`_tag`) | ERA5: Copernicus licence, free use with attribution. Open-Meteo: data under CC BY 4.0 with attribution |
| terrain heights of the depot, points and the 250 m grid | Copernicus DEM GLO-30 (30 m), read from the public `copernicus-dem-30m` bucket | `world/<city>_map.json` (`_tag`, `terrain`) | Copernicus DEM licence, free use with attribution |
| coordinates of depots, delivery points and airports | picked by hand on a map; no map tiles or OpenStreetMap data are included | `world/<city>_map.json`, `build_maps.py` | ours, CC BY 4.0 |
| radii of the no-fly circles, pads | our estimate (О) | `world/<city>_map.json` | ours, CC BY 4.0 |
| drone figures (mass, battery, hover times, range, wind and temperature limits) | DJI FlyCart 30 specifications, dji.com/flycart-30/specs; the game drone has no brand | `sim.py` (`D`, tags И/П/О) | facts, cited |

Attribution lines:

- Weather: "Contains modified Copernicus Climate Change Service information 2025. Weather data by Open-Meteo.com (CC BY 4.0)."
- Terrain: "Produced using Copernicus WorldDEM-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018 provided under COPERNICUS by the European Union and ESA; all rights reserved."

Neither the European Commission, ECMWF nor ESA is responsible for any use of this information. The raw downloads (`geo/era5`, `geo/dem`) are not in this repository; `pick_days.py` and `build_maps.py` show how the files in `world/` were made from them.
