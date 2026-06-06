# VoidIndex API

A comprehensive Mars photo API providing access to imagery from all active and completed NASA Mars missions. Around **12 million images** indexed from NASA's Planetary Data System and mission archives, with response times much faster than querying NASA directly.

**Base URL:** `https://api.voidindex.space`
**Documentation:** `https://api.voidindex.space/docs`

---

## Supported Missions

| Vehicle | Type | Mission Period | Images |
|---|---|---|---|
| Perseverance | Rover | 2021 – present | 536,530+ |
| Curiosity | Rover | 2012 – present | 1,458,592+ |
| Ingenuity | Helicopter | 2021 – 2024 | 14,553 |
| Insight | Lander | 2018 – 2022 | 6,668 |
| Opportunity | Rover | 2004 – 2019 | 4,417,342 |
| Spirit | Rover | 2004 – 2010 | 2,227,612 |
| Phoenix | Lander | 2008 - 2009 | 256,434 |
| Mars Reconnaissance Orbiter | 2005 - Present | 3,197,637 |

---

## Quickstart

```bash
# List all vehicles
curl https://api.voidindex.space/mars/vehicles

# Get the latest Curiosity images
curl https://api.voidindex.space/mars/curiosity

# Filter by camera and sol range
curl "https://api.voidindex.space/mars/perseverance?camera=MCZ_LEFT&sol_min=100&sol_max=200"

# Get Opportunity PANCAM images from a specific sol
curl "https://api.voidindex.space/mars/opportunity?camera=PANCAM_LEFT&sol=1000"

# Get statistics for Spirit
curl https://api.voidindex.space/mars/spirit/stats
```

---

## Endpoints

### `GET /mars/vehicles`
List all available vehicles.

### `GET /mars/<vehicle_name>`
Retrieve paginated images for a vehicle.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `camera` | string | — | Filter by camera code |
| `sol` | int | — | Filter by exact sol |
| `sol_min` | int | — | Minimum sol (inclusive) |
| `sol_max` | int | — | Maximum sol (inclusive) |
| `date_from` | string | — | Lower date bound (YYYY-MM-DD) |
| `date_to` | string | — | Upper date bound (YYYY-MM-DD) |
| `sort` | string | `date` | Sort field: `date`, `sol`, `camera`, `nasa_id`, `id` |
| `order` | string | `desc` | Sort direction: `asc` or `desc` |
| `page` | int | `1` | Page number |
| `limit` | int | `50` | Results per page (max 100) |

### `GET /mars/<vehicle_name>/cameras`
List all cameras available for a vehicle with full names.

### `GET /mars/<vehicle_name>/stats`
Aggregate statistics: total images, sol range, date range, and per-camera counts.

---

## Example Response

```json
{
  "vehicle": "opportunity",
  "images": [
    {
      "id": 982565,
      "nasa_id": "1m581290074ffld2fcp2935m2m1",
      "title": "Mars Opportunity Rover: Sol 5104 Microscopic Imager",
      "description": "Image taken by the Mars Opportunity Rover on Sol 5104 using the Microscopic Imager.",
      "date": "2018-06-03T09:30:39Z",
      "image_url": "https://d2gq8errdqpl02.cloudfront.net/Opportunity/...",
      "camera": "MI",
      "credit": "NASA/JPL-Caltech",
      "sol": 5104
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 50,
    "total_count": 164235,
    "total_pages": 3285,
    "has_next": true,
    "has_prev": false
  },
  "filters": { ... },
  "timestamp": "2026-05-22T21:21:40.637430"
}
```

---

## Data Sources

Image data is sourced from:
- [NASA Mars Exploration Rover mission archives](https://mars.nasa.gov)
- [NASA Planetary Data System (PDS)](https://pds.nasa.gov)

All images are credited to **NASA/JPL-Caltech** and their respective instrument teams. VoidIndex does not host the images themselves — all `image_url` values point directly to NASA's CloudFront distribution or NASA directly.

---

## License

MIT License — see [LICENSE](LICENSE) for details.