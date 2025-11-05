from django.conf import settings
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q, QuerySet
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.views.generic.edit import ModelFormMixin
from submission.models import STAGE_UNSUBMITTED, Article
from utils.setting_handler import get_setting

from .workflow import STEPS, Step


class AuthorFilteringView(UserPassesTestMixin):
    def test_func(self) -> bool:
        """
        Access to the mixing is restricted to logged-in users.

        Optionally restrict access to staff users.

        :return: If user is authorized to access the view.
        :rtype: bool
        """
        logged_in = self.request.user.is_authenticated
        if not logged_in:
            return False
        return not getattr(settings, "WJS_REQUIRE_STAFF_FOR_SUBMISSION", False) or self.request.user.is_staff

    def get_queryset(self) -> QuerySet:
        """
        Filter the base queryset to include only articles for which the current user is owner or correspondence author.

        :return: Queryset of articles.
        :rtype: QuerySet[Article]
        """
        return (
            super()
            .get_queryset()
            .filter(Q(owner=self.request.user) | Q(correspondence_author=self.request.user), stage=STAGE_UNSUBMITTED)
            .filter(journal=self.request.journal)
        )


class StepCheckView(ModelFormMixin):
    step = None
    model = Article
    context_object_name = "article"
    pk_url_kwarg = "article_id"

    @cached_property
    def _step_object(self) -> Step:
        return STEPS.get(self.step)

    def _verify_step(self, request, *args, **kwargs) -> HttpResponseRedirect | None:
        """Extract information about the current step and verify if it is active."""
        if get_setting("general", "disable_journal_submission", request.journal).processed_value:
            return HttpResponseRedirect(reverse("wjs_submission_closed"))

        if not self.kwargs.get("article_id"):
            return None
        try:
            article = self.get_object()
            active_step = self._step_object.is_active(article.journal, article, self.request.user)
            if not active_step:
                return HttpResponseRedirect(self._step_object.get_incomplete_step_url(article))
        except self.model.DoesNotExist:
            pass
        return None

    def get(self, request, *args, **kwargs):
        """Step matching the view has been completed."""
        if skip := self._verify_step(request, *args, **kwargs):
            return skip
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        """Step matching the view has been completed."""
        if skip := self._verify_step(request, *args, **kwargs):
            return skip
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Populate view context with step states."""
        context = super().get_context_data(**kwargs)
        context["steps"] = self._step_object.get_steps_states(
            journal=self.request.journal, article=self.object, user=self.request.user
        )
        context["step"] = self._step_object
        return context


class HtmxMixin:
    """Mixin to detect if request is an htmx request."""

    htmx = False

    def dispatch(self, request, *args, **kwargs):
        """
        Handle an HTTP request dispatch, detecting if the request is made by HTMX and setting the `htmx` attribute.

        This method overrides the base class dispatch method to include HTMX-specific
        logic by checking the request headers.

        :param request: The incoming HTTP request object.
        :type request: HttpRequest
        :param args: Positional arguments passed to the method.
        :param kwargs: Keyword arguments passed to the method.
        :return: The response from the base class `dispatch` method.
        :rtype: HttpResponse
        """
        if request.headers.get("HX-Request"):
            self.htmx = True
        return super().dispatch(request, *args, **kwargs)
