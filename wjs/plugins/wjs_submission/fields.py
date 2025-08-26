from pathlib import Path

from core.model_utils import MiniHTMLFormField
from django.core.files import File as DjangoFile
from django.urls import reverse
from tinymce.widgets import TinyMCE


class CoreFileWrapper(DjangoFile):
    """
    Provide a wrapper for handling a core janeway file within the Django File structure.

    This class extends the Django `File` class to provide additional functionality
    specific to core file handling, including setting the file path and URL for
    downloads.

    This file is suitable for use with the `FileField` class.

    :ivar url: URL path for downloading the core file.
    :type url: str
    """

    def __init__(self, core_file):
        """
        Initialize the object with the provided core file.

        The initializer sets up the binary file for reading and assigns a URL for file
        download based on the provided core file.

        :param core_file: Core file object to initialize with

        :raises AttributeError: If `core_file.self_article_path()` or other referenced
                                attributes do not exist
        :raises FileNotFoundError: If the file path specified by
                                   `core_file.self_article_path()` does not exist
        :raises KeyError: If `core_file.article_id` or `core_file.pk` is not accessible
        """
        file_path = Path(core_file.self_article_path())
        super().__init__(file_path.open("rb"), name=core_file.original_filename)
        self.url = reverse(
            "article_file_download",
            kwargs={"identifier_type": "id", "identifier": core_file.article_id, "file_id": core_file.pk},
        )


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
