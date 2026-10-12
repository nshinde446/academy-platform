"""Test Portal access roles.

Operational staff — device operators and floor coordinators — enter a test's
marks (upload subject/result CSVs, answer key, resolve unmatched rows) alongside
the portal admins. Teachers can view the portal and rank lists but not upload.
These assertions guard the role sets the routes depend on against regressions.
"""

from app.modules.tests.api import routes


def test_marks_entry_roles_include_operators_exclude_teacher():
    assert "device_operator" in routes._MARKS_ENTRY_ROLES
    assert "floor_coordinator" in routes._MARKS_ENTRY_ROLES
    # Admins keep access.
    for r in ("super_admin", "branch_admin", "academic_head"):
        assert r in routes._MARKS_ENTRY_ROLES
    # Teachers can view but not upload marks.
    assert "teacher" not in routes._MARKS_ENTRY_ROLES


def test_view_roles_superset_of_entry_plus_teacher():
    assert set(routes._MARKS_ENTRY_ROLES) <= set(routes._PORTAL_VIEW_ROLES)
    assert "teacher" in routes._PORTAL_VIEW_ROLES


def _route_roles(path: str, method: str) -> set[str]:
    """The role set a route's require_roles dependency was built with (captured
    in the dependency's closure)."""
    route = next(
        r for r in routes.tests_router.routes
        if r.path == path and method in r.methods
    )
    for dep in route.dependant.dependencies:
        closure = getattr(dep.call, "__closure__", None) or ()
        for cell in closure:
            val = cell.cell_contents
            if isinstance(val, (list, tuple, set)) and "super_admin" in val:
                return set(val)
    raise AssertionError(f"no role dependency found on {method} {path}")


def test_subject_upload_route_allows_operators_not_teacher():
    roles = _route_roles("/tests/{test_id}/upload-csv/{subject_id}", "POST")
    assert {"device_operator", "floor_coordinator"} <= roles
    assert "teacher" not in roles


def test_ranklist_view_route_allows_operators_and_teacher():
    roles = _route_roles("/tests/{test_id}/ranklist", "GET")
    assert {"device_operator", "floor_coordinator", "teacher"} <= roles
