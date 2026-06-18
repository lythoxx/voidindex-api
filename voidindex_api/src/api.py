from flask import Blueprint, jsonify, request, current_app, Response, g
import datetime
import mimetypes
import json
import os

import psycopg2
import psycopg2.extras


def get_db():
    if 'db' not in g:
        g.db = psycopg2.connect(
            current_app.config['DATABASE_DSN'],
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    return g.db


#: Vehicles names that are present in the database.
VEHICLES = ["perseverance", "curiosity", "ingenuity", "insight", "opportunity", "spirit", "phoenix", "mro", "viking1", "viking2", "mgs", "mariner9", "pathfinder", "sojourner", "odyssey"]

bp = Blueprint('api', __name__)


@bp.route("/mars/vehicles")
def vehicles_list():
    """List every Mars vehicle available in the database.

    **Route:** ``GET /mars/vehicles``

    :returns: JSON object with the following keys:

        - ``vehicles`` (*list[str]*) — vehicle names, e.g.
        ``["perseverance", "curiosity", ...]``.
        - ``timestamp`` (*str*) — UTC ISO-8601 timestamp of the response.

    :rtype: flask.Response
    """
    return jsonify({
        "vehicles": VEHICLES,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })


@bp.route("/mars/<vehicle_name>")
def vehicle_images(vehicle_name):
    """Retrieve paginated images for a specific Mars vehicle.

    **Route:** ``GET /mars/<vehicle_name>``

    :param vehicle_name: Vehicle name (one of :data:`VEHICLES`).
        Case-insensitive.
    :type vehicle_name: str

    **Query parameters:**

    .. list-table::
       :header-rows: 1
       :widths: 20 10 70

       * - Parameter
         - Type
         - Description
       * - ``camera``
         - str
         - Filter by exact camera code.
       * - ``sol``
         - int
         - Filter by an exact Martian sol.
       * - ``sol_min``
         - int
         - Lower bound for sol range (inclusive).  Ignored when ``sol`` is set.
       * - ``sol_max``
         - int
         - Upper bound for sol range (inclusive).  Ignored when ``sol`` is set.
       * - ``date_from``
         - str
         - Lower bound for Earth date (``YYYY-MM-DD``, inclusive).
       * - ``date_to``
         - str
         - Upper bound for Earth date (``YYYY-MM-DD``, inclusive).
       * - ``sort``
         - str
         - Column to sort by.  Allowed: ``date``, ``sol``, ``nasa_id``,
           ``camera``, ``id``.  Default: ``date``.
       * - ``order``
         - str
         - Sort direction: ``asc`` or ``desc``.  Default: ``desc``.
       * - ``page``
         - int
         - 1-based page number.  Default: ``1``.
       * - ``limit``
         - int
         - Items per page (1-100).  Default: ``50``.

    :returns: JSON object with the following keys:

        - ``vehicle`` (*str*) — normalised vehicle name.
        - ``images`` (*list[dict]*) — list of image records, each containing
          ``id``, ``nasa_id``, ``title``, ``description``, ``date``,
          ``image_url``, ``camera``, ``credit``, and ``sol``.
        - ``pagination`` (*dict*) — ``page``, ``limit``, ``total_count``,
          ``total_pages``, ``has_next``, ``has_prev``.
        - ``filters`` (*dict*) — echo of all applied filter/sort values.
        - ``timestamp`` (*str*) — UTC ISO-8601 response timestamp.

    :rtype: flask.Response
    :raises werkzeug.exceptions.NotFound: Returns HTTP 404 JSON when
        *vehicle_name* is not present in :data:`VEHICLES`.
    """

    if vehicle_name.lower() not in VEHICLES:
        return jsonify({
            "error": "Invalid vehicle name",
            "available_vehicles": VEHICLES
        }), 404

    vehicle_name = vehicle_name.lower()
    db = get_db()
    cur = db.cursor()

    camera = request.args.get('camera', type=str)
    sol_min = request.args.get('sol_min', type=int) or request.args.get('orbit_min', type=int)
    sol_max = request.args.get('sol_max', type=int) or request.args.get('orbit_max', type=int)
    sol = request.args.get('sol', type=int) or request.args.get('orbit', type=int)
    date_from = request.args.get('date_from', type=str)
    date_to = request.args.get('date_to', type=str)

    sort_by = request.args.get('sort', default='date', type=str)
    order = request.args.get('order', default='desc', type=str)
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=50, type=int)

    valid_sort_fields = ['date', 'sol', 'nasa_id', 'camera', 'id']
    if sort_by not in valid_sort_fields:
        sort_by = 'date'
    if order.lower() not in ['asc', 'desc']:
        order = 'desc'
    if page < 1:
        page = 1
    if limit < 1 or limit > 100:
        limit = 50

    where_clauses = ["1=1"]
    params = []

    if camera:
        where_clauses.append("camera = %s")
        params.append(camera)

    if sol is not None:
        where_clauses.append("sol = %s")
        params.append(sol)
    elif sol_min is not None or sol_max is not None:
        if sol_min is not None:
            where_clauses.append("sol >= %s")
            params.append(sol_min)
        if sol_max is not None:
            where_clauses.append("sol <= %s")
            params.append(sol_max)

    if date_from:
        where_clauses.append("date >= %s")
        params.append(date_from)
    if date_to:
        where_clauses.append("date <= %s")
        params.append(date_to)

    where_sql = " WHERE " + " AND ".join(where_clauses)

    has_sol_range = sol_min is not None or sol_max is not None
    has_date_filter = date_from is not None or date_to is not None

    if camera and not has_sol_range and sol is None and not has_date_filter:
        # camera_counts cache — camera only filter
        cur.execute(
            "SELECT count FROM camera_counts WHERE vehicle = %s AND camera = %s",
            (vehicle_name, camera)
        )
        row = cur.fetchone()
        total_count = row["count"] if row else 0

    elif has_sol_range and sol is None and not camera and not has_date_filter:
        # sol_counts cache — sol range only filter
        sol_min_val = sol_min if sol_min is not None else 0
        sol_max_val = sol_max if sol_max is not None else 99999
        cur.execute(
            "SELECT COALESCE(SUM(count), 0) as count FROM sol_counts WHERE vehicle = %s AND sol >= %s AND sol <= %s",
            (vehicle_name, sol_min_val, sol_max_val)
        )
        total_count = cur.fetchone()["count"]

    else:
        # fallback — live COUNT
        cur.execute(
            f"SELECT COUNT(*) as count FROM {vehicle_name}{where_sql}",
            params
        )
        total_count = cur.fetchone()["count"]

    offset = (page - 1) * limit
    cur.execute(
        f"SELECT * FROM {vehicle_name}{where_sql} ORDER BY {sort_by} {order.upper()} LIMIT %s OFFSET %s",
        (*params, limit, offset)
    )
    rows = cur.fetchall()

    images = []
    sol_field = "orbit" if vehicle_name in ["mro", "mgs", "mariner9", "odyssey"] else "sol"
    for row in rows:
        images.append({
            "id": row["id"],
            "nasa_id": row["nasa_id"],
            "title": row["title"],
            "description": row["description"],
            "date": row["date"],
            "image_url": row["image_url"],
            "camera": row["camera"],
            "credit": row["credit"],
            sol_field: row["sol"]
        })

    total_pages = (total_count + limit - 1) // limit

    return jsonify({
        "vehicle": vehicle_name,
        "images": images,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_count": total_count,
            "total_pages": total_pages,
            "has_next": page < total_pages,
            "has_prev": page > 1
        },
        "filters": {
            "camera": camera,
            "sol": sol,
            "sol_min": sol_min,
            "sol_max": sol_max,
            "date_from": date_from,
            "date_to": date_to,
            "sort_by": sort_by,
            "order": order
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    })


@bp.route("/mars/<vehicle_name>/cameras")
def vehicle_cameras(vehicle_name):
    """List every camera that has recorded images for a specific vehicle.

    **Route:** ``GET /mars/<vehicle_name>/cameras``

    :param vehicle_name: Vehicle name (one of :data:`VEHICLES`).
        Case-insensitive.
    :type vehicle_name: str

    :returns: JSON object with the following keys:

        - ``vehicle`` (*str*) — normalised vehicle name.
        - ``cameras`` (*list[dict]*) — list of camera objects, each with:

        - ``code`` (*str*) — short camera identifier (e.g. ``MCZ_LEFT``).
        - ``full_name`` (*str*) — human-readable camera name.  Falls back
            to the code if no entry exists in the ``cameras`` table.

        - ``timestamp`` (*str*) — UTC ISO-8601 response timestamp.

    :rtype: flask.Response
    :raises werkzeug.exceptions.NotFound: Returns HTTP 404 JSON when
        *vehicle_name* is not present in :data:`VEHICLES`.
    """

    if vehicle_name.lower() not in VEHICLES:
        return jsonify({
            "error": "Invalid vehicle name",
            "available_vehicles": VEHICLES
        }), 404

    vehicle_name = vehicle_name.lower()
    db = get_db()
    cur = db.cursor()

    cur.execute(f"SELECT DISTINCT camera FROM {vehicle_name} WHERE camera IS NOT NULL ORDER BY camera")
    cameras = [row["camera"] for row in cur.fetchall()]

    full_names = {}
    for camera in cameras:
        cur.execute(
            "SELECT full_name FROM cameras WHERE code = %s AND vehicle = %s",
            (camera, vehicle_name)
        )
        result = cur.fetchone()
        full_names[camera] = result["full_name"] if result else camera

    return jsonify({
        "vehicle": vehicle_name,
        "cameras": [{"code": cam, "full_name": full_names.get(cam, cam)} for cam in cameras],
        "timestamp": datetime.datetime.utcnow().isoformat()
    })



STATIC_STATS_VEHICLES = [
    "spirit", "opportunity", "phoenix", "pathfinder", "sojourner",
    "viking1", "viking2", "mariner9", "mgs", "ingenuity",
    "mro", "odyssey", "insight"
]

STATS_JSON_PATH = os.path.join(os.path.dirname(__file__), "stats.json")

@bp.route("/mars/<vehicle_name>/stats")
def vehicle_stats(vehicle_name):
    """Return aggregate statistics for a specific Mars vehicle.

    **Route:** ``GET /mars/<vehicle_name>/stats``

    :param vehicle_name: Vehicle name (one of :data:`VEHICLES`).
        Case-insensitive.
    :type vehicle_name: str

    :returns: JSON object with the following keys:

        - ``vehicle`` (*str*) — normalised vehicle name.
        - ``stats`` (*dict*) — aggregate data:

        - ``total_images`` (*int*) — total number of stored images.
        - ``sol_range`` (*dict*) — ``{ "min": int, "max": int }``.
        - ``date_range`` (*dict*) — ``{ "min": str, "max": str }``
            with ISO-8601 date strings.
        - ``cameras`` (*dict*) — mapping of camera code → image count,
            ordered by descending count.

        - ``timestamp`` (*str*) — UTC ISO-8601 response timestamp.

    :rtype: flask.Response
    :raises werkzeug.exceptions.NotFound: Returns HTTP 404 JSON when
        *vehicle_name* is not present in :data:`VEHICLES`.
    """
    if vehicle_name.lower() not in VEHICLES:
        return jsonify({
            "error": "Invalid vehicle name",
            "available_vehicles": VEHICLES
        }), 404

    vehicle_name = vehicle_name.lower()

    if vehicle_name in STATIC_STATS_VEHICLES:
        with open(STATS_JSON_PATH) as f:
            cached = json.load(f)
        if vehicle_name in cached:
            return jsonify({
                "vehicle": vehicle_name,
                "stats": cached[vehicle_name],
                "timestamp": datetime.datetime.utcnow().isoformat()
            })

    db = get_db()
    cur = db.cursor()
    stats = {}

    cur.execute(
        f"SELECT COUNT(*) as total, MIN(sol) as sol_min, MAX(sol) as sol_max, MIN(date) as date_min, MAX(date) as date_max FROM {vehicle_name}"
    )
    row = cur.fetchone()
    stats["total_images"] = row["total"]
    stats["sol_range"] = {"min": row["sol_min"], "max": row["sol_max"]}
    stats["date_range"] = {"min": row["date_min"], "max": row["date_max"]}

    cur.execute(
        "SELECT camera, count FROM camera_counts WHERE vehicle = %s ORDER BY count DESC",
        (vehicle_name,)
    )
    stats["cameras"] = {row["camera"]: row["count"] for row in cur.fetchall() if row["camera"]}

    return jsonify({
        "vehicle": vehicle_name,
        "stats": stats,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })


@bp.route("/mars")
def mars_index():
    """Return a self-describing index of all Mars endpoints and their parameters.

    **Route:** ``GET /api/mars``

    :returns: JSON object documenting available endpoints, the vehicle list,
        filtering parameters, and sorting parameters.
    :rtype: flask.Response
    """
    return jsonify({
        "message": "Welcome to the VoidIndex Mars API! Available endpoints:",
        "endpoints": {
            "/mars/vehicles": "List all available vehicles",
            "/mars/<vehicle_name>": "Get images from a specific vehicle with filtering and sorting",
            "/mars/<vehicle_name>/cameras": "Get list of available cameras for a specific vehicle",
            "/mars/<vehicle_name>/stats": "Get statistics for a specific vehicle"
        },
        "vehicles": VEHICLES,
        "filtering_parameters": {
            "camera": "Filter by camera name",
            "sol": "Filter by specific sol",
            "sol_min": "Filter by minimum sol",
            "sol_max": "Filter by maximum sol",
            "date_from": "Filter from date (YYYY-MM-DD)",
            "date_to": "Filter to date (YYYY-MM-DD)"
        },
        "sorting_parameters": {
            "sort": "Sort field (date, sol, nasa_id, camera, id) - default: date",
            "order": "Sort order (asc, desc) - default: desc"
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    })


@bp.route("/")
def index():
    """API root — return a top-level index of all available endpoints.

    **Route:** ``GET /``

    :returns: JSON object with a human-readable ``message``, an ``endpoints``
        mapping of route paths to brief descriptions, and
        ``pagination_parameters``.
    :rtype: flask.Response
    """
    return jsonify({
        "message": "Welcome to the VoidIndex API! The VoidIndex API provides access to Mars vehicle images and metadata collected from NASA's APIs. You can filter, sort, and paginate the results to find exactly what you're looking for. This API contains stripped down data from the original NASA APIs, so some fields may be missing or simplified. For more detailed information, please refer to the original NASA APIs.",
        "endpoints": {
            "/": "API index with available endpoints",
            "/mars": "List all available vehicles",
            "/mars/<vehicle_name>": "Get vehicle images (supports filtering & sorting)",
            "/mars/<vehicle_name>/cameras": "Get available cameras for a vehicle",
            "/mars/<vehicle_name>/stats": "Get statistics for a vehicle",
        },
        "pagination_parameters": {
            "page": "Page number (default: 1)",
            "limit": "Items per page (default: 50, max: 200)"
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    })


@bp.route("/docs/")
def docs_index():
    response = Response(status=200)
    response.headers["X-Accel-Redirect"] = "/_protected_docs/index.html"
    return response


@bp.route("/docs/<path:filename>")
def docs_file(filename):
    response = Response(status=200)
    response.headers["X-Accel-Redirect"] = f"/_protected_docs/{filename}"
    mime_type, _ = mimetypes.guess_type(filename)
    if mime_type:
        response.headers["Content-Type"] = mime_type
    return response