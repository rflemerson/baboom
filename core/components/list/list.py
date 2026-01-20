from django_components import component


@component.register("list")
class List(component.Component):
    template_name = "list.html"

    def get_context_data(
        self, filter_obj, page_obj=None, per_page=None, query_params=None
    ):
        return {
            "filter": filter_obj,
            "page_obj": page_obj,
            "per_page": per_page,
            "query_params": query_params or {},
        }
