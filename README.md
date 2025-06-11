# WJS submission

Janeway plugin to manage submissions for WJS.

Includes
- Import from ArXiv
- Hierarchical keywords
- Extended file / content type support
- Improved funding process
- Support for Collaborations


## Install

Being a Janeway plugin, this code should be made available to Janeway in the `plugins` folder.

One can proceed as follow:
- install the package
- give Janeway access to the plugin (link the plugin into Janeway's `plugins` dir)
- install the plugins

E.g.
```sh
pip install -e .[test]
ln -s ...venv/.../wjs_submission ...janeway/src/plugins/
python -m manage install_plugins
```

**NB**: link the plugin manually and do not use WJS's `link_plugins`: it does not work if the packages are installed in edit-mode (with `-e`).
