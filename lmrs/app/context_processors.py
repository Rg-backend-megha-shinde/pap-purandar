from django.conf import settings


def geoserver(request):
    """GeoServer endpoint and workspaces used by the map templates.

    Supplied globally so any view rendering home.html (or a template extending
    it, such as dashboard.html) gets the configuration without repeating it.
    """
    return {
        'geoserver_url': settings.GEOSERVER_URL,
        'geoserver_workspace': settings.GEOSERVER_WORKSPACE,
        'geoserver_purandar_workspace': settings.GEOSERVER_PURANDAR_WORKSPACE,
        'geoserver_legacy_workspace': settings.GEOSERVER_LEGACY_WORKSPACE,
    }
