from django.views.generic import UpdateView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView


class SubmissionStep4View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 4
    template_name = "wjs_submission/step4/article_form.html"
    fields = "__all__"
