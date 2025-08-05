from core.model_utils import MiniHTMLFormField
from tinymce.widgets import TinyMCE


class WjsMiniHTMLFormField(MiniHTMLFormField):
    def __init__(self, *args, **kwargs):
        """
        Initialize the instance and configure default attributes and options for content sanitization.

        :param args: Positional arguments passed to the base class initializer.
        :param kwargs: Keyword arguments passed to the base class initializer.
            Extracts `height` with a default value of "30rem" if not specified.
        """
        height = kwargs.pop("height", "30rem")
        super().__init__(*args, **kwargs)
        self.bleach_options["tags"] = [
            "a",
            "b",
            "br",
            "div",
            "em",
            "i",
            "li",
            "ol",
            "p",
            "span",
            "strong",
            "sub",
            "sup",
            "u",
        ]
        self.bleach_options["attributes"] = {"a": ["href", "title", "target"]}
        if isinstance(self.widget, TinyMCE):
            self.widget.mce_attrs.update(
                {
                    "plugins": "link lists charmap",
                    "menubar": "",
                    "forced_root_block": "div",
                    "toolbar": "bold italic link numlist charmap",
                    "height": height,
                    "resize": True,
                    "elementpath": False,
                    "paste_data_images": False,
                }
            )
