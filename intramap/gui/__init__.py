"""Interface graphique PySide6 pour IntraMap.

Le module GUI est une couche additive au-dessus du cœur CLI : il réutilise
``intramap.models``, ``intramap.inventory`` et ``intramap.scanner`` sans les
modifier. Les positions des nœuds sur le canvas sont stockées dans un fichier
*sidecar* JSON (voir :mod:`intramap.gui.layout`) afin de ne pas toucher au
schéma YAML strict de l'inventaire.
"""
