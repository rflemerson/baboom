from django_components import component


@component.register("header")
class Header(component.Component):
    template_name = "header.html"
