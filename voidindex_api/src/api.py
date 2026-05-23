from flask import Blueprint, jsonify, request, current_app, Response
import datetime
import sqlite3
import mimetypes

def get_db():
    connection = sqlite3.connect(current_app.config["DATABASE"])
    connection.row_factory = sqlite3.Row
    return connection


#: Vehicles names that are present in the database.
VEHICLES = ["perseverance", "curiosity", "ingenuity", "insight", "opportunity", "spirit"]

bp = Blueprint('api', __name__)

@bp.route("/mars/vehicles")
def vehicles_list():
    """List every Mars vehicle available in the database.

    **Route:** ``GET /api/mars/vehicles``

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

    **Route:** ``GET /api/mars/<vehicle_name>``

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

    # Validate vehicle name
    if vehicle_name.lower() not in VEHICLES:
        return jsonify({
            "error": "Invalid vehicle name",
            "available_vehicles": VEHICLES
        }), 404

    vehicle_name = vehicle_name.lower()
    db = get_db()

    # Get query parameters for filtering
    camera = request.args.get('camera', type=str)
    sol_min = request.args.get('sol_min', type=int)
    sol_max = request.args.get('sol_max', type=int)
    sol = request.args.get('sol', type=int)
    date_from = request.args.get('date_from', type=str)
    date_to = request.args.get('date_to', type=str)

    # Get query parameters for sorting and pagination
    sort_by = request.args.get('sort', default='date', type=str)
    order = request.args.get('order', default='desc', type=str)
    page = request.args.get('page', default=1, type=int)
    limit = request.args.get('limit', default=50, type=int)

    # Validate sort_by
    valid_sort_fields = ['date', 'sol', 'nasa_id', 'camera', 'id']
    if sort_by not in valid_sort_fields:
        sort_by = 'date'

    # Validate order
    if order.lower() not in ['asc', 'desc']:
        order = 'desc'

    # Validate pagination
    if page < 1:
        page = 1
    if limit < 1 or limit > 100:
        limit = 50

    # Build query
    query = f"SELECT * FROM {vehicle_name} WHERE 1=1"
    params = []

    # Apply filters
    if camera:
        query += " AND camera = ?"
        params.append(camera)

    if sol is not None:
        query += " AND sol = ?"
        params.append(sol)
    elif sol_min is not None or sol_max is not None:
        if sol_min is not None:
            query += " AND sol >= ?"
            params.append(sol_min)
        if sol_max is not None:
            query += " AND sol <= ?"
            params.append(sol_max)

    if date_from:
        query += " AND date >= ?"
        params.append(date_from)

    if date_to:
        query += " AND date <= ?"
        params.append(date_to)

    # Add sorting
    query += f" ORDER BY {sort_by} {order.upper()}"

    # Get total count before pagination
    count_query = query.replace(f"SELECT * FROM {vehicle_name}", f"SELECT COUNT(*) FROM {vehicle_name}")
    total_count = db.execute(count_query, params).fetchone()[0]

    # Add pagination
    offset = (page - 1) * limit
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    # Execute query
    cursor = db.execute(query, params)
    rows = cursor.fetchall()

    # Convert rows to dictionaries
    images = []
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
            "sol": row["sol"]
        })

    # Calculate pagination metadata
    total_pages = (total_count + limit - 1) // limit  # Ceiling division

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

    **Route:** ``GET /api/mars/<vehicle_name>/cameras``

    Camera records are sourced from the ``cameras`` reference table and
    cross-referenced with the distinct camera codes present in the vehicle's
    image table, so only cameras with at least one image are returned.

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

    # Get distinct cameras
    cursor = db.execute(f"SELECT DISTINCT camera FROM {vehicle_name} WHERE camera IS NOT NULL ORDER BY camera")
    cameras = [row[0] for row in cursor.fetchall()]
    full_names = {}
    for camera in cameras:
        cursor = db.execute("SELECT full_name FROM cameras WHERE code = ? and vehicle = ?", (camera,vehicle_name))
        result = cursor.fetchone()
        full_names[camera] = result[0] if result else camera

    return jsonify({
        "vehicle": vehicle_name,
        "cameras": [{"code": cam, "full_name": full_names.get(cam, cam)} for cam in cameras],
        "timestamp": datetime.datetime.utcnow().isoformat()
    })

@bp.route("/mars/<vehicle_name>/stats")
def vehicle_stats(vehicle_name):
    """Return aggregate statistics for a specific Mars vehicle.

    **Route:** ``GET /api/mars/<vehicle_name>/stats``

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
    db = get_db()

    # Get stats
    stats = {}

    # Total images
    cursor = db.execute(f"SELECT COUNT(*) FROM {vehicle_name}")
    stats["total_images"] = cursor.fetchone()[0]

    # Sol range
    cursor = db.execute(f"SELECT MIN(sol), MAX(sol) FROM {vehicle_name}")
    sol_min, sol_max = cursor.fetchone()
    stats["sol_range"] = {"min": sol_min, "max": sol_max}

    # Date range
    cursor = db.execute(f"SELECT MIN(date), MAX(date) FROM {vehicle_name}")
    date_min, date_max = cursor.fetchone()
    stats["date_range"] = {"min": date_min, "max": date_max}

    # Camera counts
    cursor = db.execute(f"SELECT camera, COUNT(*) as count FROM {vehicle_name} GROUP BY camera ORDER BY count DESC")
    stats["cameras"] = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

    return jsonify({
        "vehicle": vehicle_name,
        "stats": stats,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })


@bp.route("/mars")
def mars_index():
    """Return a self-describing index of all Mars endpoints and their parameters.

    **Route:** ``GET /api/mars``

    Useful as a discovery endpoint for clients unfamiliar with the API.
    The response mirrors the full set of query parameters accepted by
    :func:`vehicle_images`.

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

    **Route:** ``GET /api/``

    Entry point for clients exploring the API.  Lists every route grouped by
    resource type together with supported pagination parameters.

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
    print("docs_index called")
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