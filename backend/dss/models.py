from django.db import models


class ActionLog(models.Model):
    """Log các hành động người dùng bấm Apply trong DSS Action Center."""

    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=40)  # auto_reroute | extend_promise | email_carrier
    route = models.CharField(max_length=20)
    level = models.CharField(max_length=10, blank=True)
    detail = models.TextField(blank=True)

    class Meta:
        db_table = "dss_action_log"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} · {self.route}"
