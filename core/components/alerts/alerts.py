from django_components import component


@component.register("alerts")
class Alerts(component.Component):
    template_name = "alerts.html"

    def get_context_data(self, alert_messages=None):
        return {
            "alert_messages": alert_messages,
        }
