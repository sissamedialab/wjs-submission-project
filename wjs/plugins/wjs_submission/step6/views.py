from django.views.generic import UpdateView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView


class SubmissionStep6View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 6
    template_name = "wjs_submission/step6/article_form.html"
    fields = "__all__"
