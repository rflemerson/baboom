from django_components import component


@component.register("list")
class ProductList(component.Component):
    template_name = "list.html"

    def get_context_data(self, filter_obj, request, page_obj=None, per_page=None):
        return {
            "filter": filter_obj,
            "component_request": request,
            "page_obj": page_obj,
            "per_page": per_page,
        }
