from django.urls import path
from .views import *

urlpatterns = [
    path('list-invoice/', HomeView.as_view(), name='home'),
    path('', AddInvoiceView.as_view(), name='add-invoice'),
    path('receipt/', ReceiptView.as_view(), name='receipt'),
    path('journal/', JournalView.as_view(), name='journal'),
    path('depense/', DepenseView.as_view(), name='depense'),
    path('bilan/', BilanView.as_view(), name='bilan'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('api/weekly-visits/', weekly_visits_data, name='weekly_visits_data'),
    path('login/', CustomLoginView.as_view(), name='login'),
    path('logout/', CustomLogoutView.as_view(), name='logout'),
    path('get-service-price/<int:service_id>/', ServicePriceView.as_view(), name='get_service_price'),
    path('parametre/', ParametreView.as_view(), name='parametre'),
    path('parametre/<str:page>/', ParametreView.as_view(), name='parametre_page'),
    path('delete_user/<int:user_id>/', DeleteUserView.as_view(), name='delete_user'),
    path('delete_service/<int:service_id>/', DeleteServiceView.as_view(), name='delete_service'),
    path('delete_inpute/<int:inpute_id>/', DeleteInputeView.as_view(), name='delete_inpute'),
    path('delete_exit/<int:exit_id>/', DeleteExitView.as_view(), name='delete_exit'),
    path('delete-depense/<int:depense_id>/', DeleteDepenseView.as_view(), name='delete_depense'),
    path('delete_invoice/<int:pk>/', DeleteInvoiceView.as_view(), name='delete_invoice'),
    path('send-invoice/<int:invoice_id>/', SendInvoiceView.as_view(), name='send_invoice'),
]
