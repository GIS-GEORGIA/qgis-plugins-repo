def classFactory(iface):
    from .transliterator_plugin import TransliteratorPlugin
    return TransliteratorPlugin(iface)