from django_components import component


@component.register("product_list_v2")
class ProductList(component.Component):
    template_name = "product_list_v3.html"

    def get_context_data(self, filter_obj, request, page_obj=None, per_page=None):
        return {
            "filter": filter_obj,
            "component_request": request,
            "page_obj": page_obj,
            "per_page": per_page,
        }
