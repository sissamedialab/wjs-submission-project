import dataclasses

from django.core.exceptions import ValidationError
from django.utils.module_loading import import_string
from submission.models import Article, KeywordArticle

from .. import settings as submission_settings


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
            self.article.journal.code,
            submission_settings.KEYWORD_VALIDATORS.get(None, []),
        )
        for validator in validators:
            ok, error = import_string(validator)(
                keyword_weights, self.article.journal, self.article.submission_data.arxiv_category
            )
            if not ok:
                raise ValidationError(error)
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

    @property
    def hierarchical(self) -> bool:
        """Tell whether the article's journal uses weighted, hierarchical keywords."""
        return self.article.journal.submissionconfiguration.hierarchical_keywords

    def get_keyword_weights(self) -> dict:
        """
        Return the keyword selection to validate, as a dictionary of keyword_id -> weight.

        Hierarchical journals post a weight for each keyword. Other journals post no weights: their keywords are
        already stored on the article by the form, so they are returned with no weight.

        :raises ValidationError: If the posted weights are malformed.
        """
        if self.hierarchical:
            return self.parse_keyword_weights()
        return dict.fromkeys(self.article.keywords.values_list("pk", flat=True))

    def run(self):
        """
        Execute the full flow: get the keyword selection, validate it, and persist the weights.

        Weights are persisted only for hierarchical journals; the other journals are validated on the keywords
        already stored by the form.

        :raises ValidationError: If parsing or validation fails.
        """
        keyword_weights = self.get_keyword_weights()
        self.run_validator(keyword_weights)
        if self.hierarchical:
            self.persist(keyword_weights)
