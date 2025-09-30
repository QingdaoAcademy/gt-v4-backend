from rest_framework.pagination import PageNumberPagination as _PageNumberPagination


class PageNumberPagination(_PageNumberPagination):
    page_size_query_param = "page_size"
    page_size = 20
    max_page_size = 100


class PageNumberPagination_10(_PageNumberPagination):
    page_size_query_param = "page_size"
    page_size = 10
    max_page_size = 10
