import dataclasses

from django.core.exceptions import ValidationError
from django.utils.module_loading import import_string
from submission.models import Article, KeywordArticle

from . import settings as submission_settings


@dataclasses.dataclass
class HandleKeywordSelection:
    article: Article
    data: dict

    def parse_keyword_weights(self):
        """
        Parse the keyword weight fields from the POST request data.

        Expects keys in the format "keyword_<keyword_id>_weight" and values as lists
        containing a single integer string among {25, 50, 75, 100}.

        :raises ValidationError: If a value is not convertible to integer, outside
        the allowed range, or if the payload is malformed.

        :return: Dictionary mapping keyword IDs to their integer weights.
        """
        data = {}
        for key, value in self.data.lists():
            if key.startswith("keyword_") and key.endswith("_weight"):
                try:
                    keyword_id = int(key.split("_")[1])
                    if not value:
                        msg = f"Missing weight value for '{key}'"
                        raise ValidationError(msg)
                    weight = int(value[0])
                    if weight not in {25, 50, 75, 100}:
                        raise ValidationError("Corrupted weight data")
                except (ValueError, TypeError):
                    msg = f"Invalid keyword weight data for field '{key}': {value!r}"
                    raise ValidationError(msg) from None
                data[keyword_id] = weight
        return data

    def run_validator(self, keyword_weights: dict):
        """
        Run all configured validators for the article's journal.

        :param keyword_weights: Dictionary of keyword_id
        :raises ValidationError: If any validator fails.
        :return: True if all validators pass.
        """
        validators = submission_settings.KEYWORD_VALIDATORS.get(
            self.article.journal,
            submission_settings.KEYWORD_VALIDATORS.get(None, []),
        )
        for validator in validators:
            ok, error = import_string(validator)(
                keyword_weights, self.article.journal, self.article.submission_data.arxiv_category
            )
            if not ok:
                return ValidationError(error)
        return True

    def persist(self, keyword_weights):
        """
        Persist KeywordArticle instances for the current article, based on keyword weights.

        The deletion of existing KeywordArticle entries for this article is handled by KeywordModelForm.

        :param keyword_weights: Dictionary of keyword_id -> weight.
        """
        KeywordArticle.objects.bulk_create(
            [
                KeywordArticle(
                    article=self.article,
                    keyword_id=keyword_id,
                    weight=weight,
                    order=order,
                )
                for order, (keyword_id, weight) in enumerate(keyword_weights.items(), start=1)
            ]
        )

    def run(self):
        """
        Execute the full flow: parse keyword weights, validate them, and persist the results.

        :raises ValidationError: If parsing or validation fails.
        """
        keyword_weights = self.parse_keyword_weights()
        self.run_validator(keyword_weights)
        self.persist(keyword_weights)
