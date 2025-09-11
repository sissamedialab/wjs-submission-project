from django.views.generic import UpdateView
from submission.models import Article

from ..mixins import AuthorFilteringView, StepCheckView


class SubmissionStep7View(AuthorFilteringView, StepCheckView, UpdateView):
    model = Article
    step = 7
    template_name = "wjs_submission/step7/article_form.html"
    fields = "__all__"
