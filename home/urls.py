from django.urls import path
from django.contrib.auth import views as auth_views
from home.views import livro_razao, livro_diario_view, registrar_are_json, dre_view, contas_are_api, are_view, index, cadastrar_view, login_view, patrimonio_view, contato, lancamento_view, contas, logout_view, perfil, editar_perfil, contas_api, registrar_lancamentos_json

urlpatterns = [
    path('', index, name= 'home'),
    path('login/', login_view, name= 'login'),
    path('logout/', logout_view, name='logout'),
    path('cadastrar/', cadastrar_view, name='cadastrar'),
    path('patrimonio/', patrimonio_view, name= 'balanco'),
    path('contato/', contato, name= 'contato'),
    path('lancamento/', lancamento_view, name= 'lancamento'),
    path('contas/criar/', contas, name= 'contas'),
    path('perfil/', perfil, name='perfil'),
    path('senha-reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('senha-reset-enviado/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('senha-reset-confirmar/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('senha-reset-completo/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('editar-perfil/', editar_perfil, name='editarperfil'),
    path('api/contas/', contas_api, name='contas_api'),
    path('lancamentos/', registrar_lancamentos_json, name='registrar_lancamentos_json'),
    path('are/', are_view, name='are'),
    path('api/contas_are/', contas_are_api, name='contas_are_api'),
    path('lancamentos_are/', registrar_are_json, name='registrar_are_json'),
    path('dre/', dre_view, name='dre'),
    path('livro_diario/', livro_diario_view, name='livro_diario'),
    path('livro_razao/', livro_razao, name='livro_razao'),
]