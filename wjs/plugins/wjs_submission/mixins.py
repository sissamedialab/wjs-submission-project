from django.http import HttpResponseRedirect
from django.utils.functional import cached_property
from django.views.generic.edit import ModelFormMixin
from submission.models import Article

from .workflow import STEPS, Step


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
        try:
            article = self.get_object()
            active_step = self._step_object.is_active(article.journal, article)
            if not active_step:
                return HttpResponseRedirect(self._step_object.get_next_step(article))
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
        context["steps"] = self._step_object.get_steps_states(self.request.journal)
        context["step"] = self._step_object
        return context


class HtmxMixin:
    """Mixin to detect if request is an htmx request."""

    htmx = False

    def dispatch(self, request, *args, **kwargs):
        if request.headers.get("HX-Request"):
            self.htmx = True
        return super().dispatch(request, *args, **kwargs)
