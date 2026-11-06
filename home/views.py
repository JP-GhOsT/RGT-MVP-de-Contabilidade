from django.shortcuts import render, redirect
from django.db.models import Sum, F, Value
from django.db.models.functions import Coalesce
from django.db.models import Case, When
from django.db import transaction
from django.db.models import DecimalField
from django.views.decorators.csrf import csrf_exempt
from home.models import Conta, Lancamento, LancamentoItem
from django.http import JsonResponse
import json
from decimal import Decimal
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import UserForm, ProfileForm
from django.views.decorators.http import require_GET
from django.forms import ValidationError
from django.utils.timezone import now
from django.core.paginator import Paginator
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

def index(request):
    return render(request, 'home/index.html')

def validar_contas_obrigatorias(codigos):
    """
    Verifica se todas as contas com os códigos fornecidos existem.
    Lança ValueError com mensagem clara se alguma estiver ausente.
    """
    contas_ausentes = []
    for codigo in codigos:
        if not Conta.objects.filter(codigo=codigo).exists():
            contas_ausentes.append(codigo)

    if contas_ausentes:
        raise ValueError(f"As seguintes contas obrigatórias estão ausentes: {', '.join(contas_ausentes)}")

def login_view(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        senha = request.POST.get('senha')

        # Como o auth padrão usa username, tentamos buscar o username pelo email:
        try:
            user = User.objects.get(email=email)
            username = user.username
        except User.DoesNotExist:
            messages.error(request, 'Usuário não encontrado.')
            return redirect('login')

        user = authenticate(request, username=username, password=senha)

        if user is not None:
            login(request, user)
            return redirect('home')  # Redirecione para a página principal após login
        else:
            messages.error(request, 'Email ou senha incorretos.')
            return redirect('login')

    return render(request, 'home/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')

def cadastrar_view(request):
    if request.method == 'POST':
        nome = request.POST.get('nome')
        email = request.POST.get('email')
        senha = request.POST.get('senha')

        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email já cadastrado.')
            return redirect('cadastrar')

        username = email.split('@')[0]  # Exemplo simples para username

        user = User.objects.create_user(username=username, email=email, password=senha, first_name=nome)
        user.save()
        messages.success(request, 'Cadastro realizado com sucesso! Faça login.')
        return redirect('login')

    return render(request, 'home/login.html')

@login_required
def patrimonio_view(request):
    contas = Conta.objects.annotate(
        total_debitos=Coalesce(Sum(
            Case(When(itens_lancamento__tipo='debito', then='itens_lancamento__valor'),
                 default=Decimal('0'),
                 output_field=DecimalField())
        ), Decimal('0')),
        total_creditos=Coalesce(Sum(
            Case(When(itens_lancamento__tipo='credito', then='itens_lancamento__valor'),
                 default=Decimal('0'),
                 output_field=DecimalField())
        ), Decimal('0'))
    ).order_by('codigo')

    for conta in contas:
        if conta.natureza == 'devedora':
            conta.saldo_calc = conta.total_debitos - conta.total_creditos
        else:
            conta.saldo_calc = conta.total_creditos - conta.total_debitos

    contas_por_tipo = {
        'ativo': [c for c in contas if c.tipo == 'ativo'],
        'passivo': [c for c in contas if c.tipo == 'passivo'],
        'patrimonio_liquido': [c for c in contas if c.tipo == 'patrimonio_liquido'],
    }

    totais = {
        'ativo': sum(c.saldo_calc for c in contas_por_tipo['ativo']),
        'passivo': sum(c.saldo_calc for c in contas_por_tipo['passivo']),
        'patrimonio_liquido': sum(c.saldo_calc for c in contas_por_tipo['patrimonio_liquido']),
    }

    balanco_equilibrado = totais['ativo'] == (totais['passivo'] + totais['patrimonio_liquido'])
    context = {
        'contas_por_tipo': contas_por_tipo,
        'totais': totais,
        'balanco_equilibrado': balanco_equilibrado
    }

    return render(request, 'home/patrimonio.html', context)

@login_required
def dre_view(request):
    # Calcular todas as contas e valores
    contas = Conta.objects.filter(tipo__in=['receita', 'custo', 'despesa']).annotate(
        total_debitos=Coalesce(Sum(
            Case(When(itens_lancamento__tipo='debito', then='itens_lancamento__valor'),
                 default=Decimal('0'),
                 output_field=DecimalField())
        ), Decimal('0')),

        total_creditos=Coalesce(Sum(
            Case(When(itens_lancamento__tipo='credito', then='itens_lancamento__valor'),
                 default=Decimal('0'),
                 output_field=DecimalField())
        ), Decimal('0'))
    )

    contas_receitas = []
    contas_custos = []
    contas_despesas_operacionais = []
    contas_outras = []

    total_receitas = Decimal('0')
    total_custos = Decimal('0')
    total_despesas_operacionais = Decimal('0')
    total_outras = Decimal('0')

    for conta in contas:
        saldo = conta.total_debitos - conta.total_creditos if conta.natureza == 'devedora' else conta.total_creditos - conta.total_debitos
        conta.valor_dre = saldo

        if conta.tipo == 'receita':
            contas_receitas.append(conta)
            total_receitas += saldo
        elif conta.tipo == 'custo':
            contas_custos.append(conta)
            total_custos += saldo
        elif conta.tipo == 'despesa':
            contas_despesas_operacionais.append(conta)
            total_despesas_operacionais += saldo
        else:
            contas_outras.append(conta)
            total_outras += saldo

    lucro_bruto = total_receitas - total_custos
    resultado_operacional = lucro_bruto - total_despesas_operacionais
    lucro_liquido = resultado_operacional + total_outras

    # Se for POST, lançar o lucro/prejuízo no patrimônio
    if request.method == 'POST':
        encerrar_resultado_do_exercicio(timezone.now())  # Zera as contas de resultado
        concluir_are(lucro_liquido)                      # Transfere para PL
        return redirect('dre')

    return render(request, 'home/dre.html', {
        'contas_receitas': contas_receitas,
        'total_receitas': total_receitas,
        'contas_custos': contas_custos,
        'total_custos': total_custos,
        'contas_despesas_operacionais': contas_despesas_operacionais,
        'total_despesas_operacionais': total_despesas_operacionais,
        'contas_outras': contas_outras,
        'total_outras': total_outras,
        'lucro_bruto': lucro_bruto,
        'resultado_operacional': resultado_operacional,
        'lucro_liquido': lucro_liquido
    })

@transaction.atomic
def encerrar_resultado_do_exercicio(data_encerramento):
    CODIGO_CONTA_RESULTADO_EXERCICIO = '3.99'

    # Verifica se a conta de resultado existe
    validar_contas_obrigatorias([CODIGO_CONTA_RESULTADO_EXERCICIO])
    contas_resultado = Conta.objects.filter(tipo__in=['receita', 'despesa', 'custo'])

    lancamento = Lancamento.objects.create(
        descricao='Encerramento das contas de resultado',
        data=data_encerramento
    )

    conta_resultado_exercicio = Conta.objects.get(codigo=CODIGO_CONTA_RESULTADO_EXERCICIO)  # Resultado do Exercício

    for conta in contas_resultado:
        total_debitos = sum(item.valor for item in conta.itens_lancamento.filter(tipo='debito'))
        total_creditos = sum(item.valor for item in conta.itens_lancamento.filter(tipo='credito'))

        saldo = total_debitos - total_creditos if conta.natureza == 'devedora' else total_creditos - total_debitos

        if saldo != 0:
            tipo_inverso = 'credito' if conta.natureza == 'devedora' else 'debito'
            
            # Zera a conta de resultado
            LancamentoItem.objects.create(
                lancamento=lancamento,
                conta=conta,
                tipo=tipo_inverso,
                valor=abs(saldo)
            )

            # Contrapartida no Resultado do Exercício
            LancamentoItem.objects.create(
                lancamento=lancamento,
                conta=conta_resultado_exercicio,
                tipo='debito' if tipo_inverso == 'credito' else 'credito',
                valor=abs(saldo)
            )

@transaction.atomic
def concluir_are(lucro_liquido):
    if lucro_liquido == 0:
        return

    CODIGO_CONTA_RESULTADO_EXERCICIO = '3.99'
    CODIGO_CONTA_PL = '2.1'

    # Validação antes de continuar
    validar_contas_obrigatorias([CODIGO_CONTA_RESULTADO_EXERCICIO, CODIGO_CONTA_PL])

    conta_resultado = Conta.objects.get(codigo=CODIGO_CONTA_RESULTADO_EXERCICIO)
    conta_pl = Conta.objects.get(codigo=CODIGO_CONTA_PL)

    lancamento = Lancamento.objects.create(
        descricao='Lançamento do Resultado do Exercício',
        data=timezone.now()
    )

    if lucro_liquido > 0:
        # Lucro: resultado -> patrimônio
        LancamentoItem.objects.create(
            lancamento=lancamento,
            conta=conta_resultado,
            valor=lucro_liquido,
            tipo='debito'
        )
        LancamentoItem.objects.create(
            lancamento=lancamento,
            conta=conta_pl,
            valor=lucro_liquido,
            tipo='credito'
        )
    else:
        # Prejuízo: patrimônio -> resultado
        lucro_liquido = abs(lucro_liquido)
        LancamentoItem.objects.create(
            lancamento=lancamento,
            conta=conta_pl,
            valor=lucro_liquido,
            tipo='debito'
        )
        LancamentoItem.objects.create(
            lancamento=lancamento,
            conta=conta_resultado,
            valor=lucro_liquido,
            tipo='credito'
        )

@login_required
def livro_diario_view(request):
    # Recuperando os lançamentos do banco de dados
    lancamentos = Lancamento.objects.all().order_by('data')

    # Processando os dados de forma que apareçam os lançamentos completos com os itens
    lancamentos_completos = []
    for lancamento in lancamentos:
        for item in lancamento.itens.all():
            lancamentos_completos.append({
                'data': lancamento.data,
                'descricao': lancamento.descricao,
                'conta': item.conta.nome,
                'tipo': item.tipo,
                'valor': item.valor,
            })

    # Passando os dados para o template
    context = {
        'lancamentos': lancamentos_completos
    }

    return render(request, 'home/livro_diario.html', context)

def contato(request):
    return render(request, 'home/contato.html')

@login_required
def contas(request):
    contas_existentes = Conta.objects.all()

    if request.method == "POST":
        codigo = request.POST.get('codigo')
        nome = request.POST.get('nome')
        tipo = request.POST.get('tipo')

        # Define a natureza automaticamente com base no tipo
        natureza = None
        tipo_lower = tipo.lower()
        if tipo_lower in ['ativo', 'despesa', 'custo']:
            natureza = 'devedora'
        elif tipo_lower in ['passivo', 'patrimonio_liquido', 'receita', 'receita']:
            natureza = 'credora'
        else:
            natureza = 'devedora'  # padrão caso queira

        # Cria a conta sem conta pai, sintetica, etc
        Conta.objects.create(
            codigo=codigo,
            nome=nome,
            tipo=tipo,
            natureza=natureza
        )

        return redirect('contas')

    context = {
        'contas_existentes': contas_existentes
    }
    return render(request, 'home/contas.html', context)

@login_required
def are_view(request):
    contas = Conta.objects.filter(tipo__in=['receita', 'custo', 'despesa'])

    if request.method == 'POST':
        conta_id = request.POST.get('conta')
        valor = float(request.POST.get('valor'))
        tipo = request.POST.get('tipo')
        data = request.POST.get('data')
        descricao = request.POST.get('descricao', '')

        if tipo == 'saida':
            valor = -abs(valor)  # transforma em valor negativo

        Lancamento.objects.create(
            conta_id=conta_id,
            valor=valor,
            descricao=descricao,
            data=data
        )

        return redirect('are')  # redireciona para limpar o formulário

    return render(request, 'home/are.html', {'contas': contas})

@login_required
def livro_razao(request):
    contas = Conta.objects.all()
    paginator = Paginator(contas, 2)  # 2 contas por página (ajuste se quiser)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "home/livro_razao.html", {
        "contas": page_obj.object_list,
        "page_obj": page_obj,
    })

@login_required
def lancamento_view(request):
    contas = Conta.objects.exclude(tipo__in=['custo', 'despesa', 'receita']).order_by('nome')
 
    if request.method == "POST":
        descricao = request.POST.get('descricao')
        data = request.POST.get('data')
 
        contas_ids = request.POST.getlist('conta[]')
        tipos = request.POST.getlist('tipo[]')
        valores = request.POST.getlist('valor[]')
 
        itens = []
        total_debito = 0
        total_credito = 0
 
        try:
            for conta_id, tipo, valor in zip(contas_ids, tipos, valores):
                conta = Conta.objects.get(id=conta_id)
                if conta.tipo in ['custo', 'despesa', 'receita']:
                    raise ValidationError(f"A conta '{conta.nome}' do tipo '{conta.tipo}' não pode ser lançada.")
                valor_decimal = Decimal(valor)
 
                if tipo == 'debito':
                    total_debito += valor_decimal
                elif tipo == 'credito':
                    total_credito += valor_decimal
                else:
                    raise ValidationError("Tipo inválido.")
 
                itens.append({
                    'conta': conta,
                    'tipo': tipo,
                    'valor': valor_decimal
                })
 
            if total_debito != total_credito:
                context = {'contas': contas, 'error': 'Lançamento não está balanceado (Débito ≠ Crédito)'}
                return render(request, 'home/lancamento.html', context)
 
            with transaction.atomic():
                lancamento = Lancamento.objects.create(descricao=descricao, data=data)
 
                for item in itens:
                    lancamento.itens.create(
                        conta=item['conta'],
                        tipo=item['tipo'],
                        valor=item['valor']
                    )
 
            return redirect('lancamento')
 
        except Exception as e:
            context = {'contas': contas, 'error': str(e)}
            return render(request, 'home/lancamento.html', context)
 
    return render(request, 'home/lancamento.html', {'contas': contas})

@csrf_exempt
@login_required
def registrar_lancamentos_json(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            lancamentos = data.get('lancamentos', [])

            if not lancamentos:
                return JsonResponse({'detail': 'Nenhum lançamento enviado.'}, status=400)

            total_debito = Decimal('0')
            total_credito = Decimal('0')
            itens = []

            for item in lancamentos:
                conta_id = item.get('conta')
                descricao = item.get('descricao', '').strip()
                valor = Decimal(str(item.get('valor', '0')))
                data_lanc = item.get('data')

                # Auto-identificar tipo com base na conta se necessário
                conta = Conta.objects.get(id=conta_id)

                # Verifica se a natureza da conta influencia o tipo
                if conta.natureza == 'devedora':
                    tipo = 'debito'
                    total_debito += valor
                else:
                    tipo = 'credito'
                    total_credito += valor

                itens.append({
                    'conta': conta,
                    'descricao': descricao,
                    'valor': valor,
                    'tipo': tipo,
                    'data': data_lanc
                })

            if total_debito != total_credito:
                return JsonResponse({'detail': 'Lançamento não balanceado. Débitos ≠ Créditos.'}, status=400)

            with transaction.atomic():
                descricao_geral = itens[0]['descricao'] if itens else ''
                data = itens[0]['data'] if itens else None
                lancamento = Lancamento.objects.create(descricao=descricao_geral, data=data)

                for item in itens:
                    lancamento.itens.create(
                        conta=item['conta'],
                        tipo=item['tipo'],
                        valor=item['valor']
                    )

            return JsonResponse({'detail': 'Lançamentos registrados com sucesso!'})

        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=400)
    
    return JsonResponse({'detail': 'Método não permitido'}, status=405)

@login_required
def contas_are_api(request):
    contas = Conta.objects.filter(tipo__in=['custo', 'despesa', 'receita'],)
    data = []
    for conta in contas:
        data.append({
            'id': conta.id,
            'codigo': conta.codigo,
            'nome': conta.nome,
            'tipo': conta.tipo,
            'natureza': conta.natureza,
            'saldo': conta.saldo,
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
@login_required
def registrar_are_json(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            lancamentos = data.get('lancamentos', [])

            if not lancamentos:
                return JsonResponse({'detail': 'Nenhum lançamento enviado.'}, status=400)

            total_debito = Decimal('0')
            total_credito = Decimal('0')
            itens = []

            for item in lancamentos:
                conta_id = item.get('conta')
                descricao = item.get('descricao', '').strip()
                valor = Decimal(str(item.get('valor', '0')))
                data_lanc = item.get('data')

                # Auto-identificar tipo com base na conta se necessário
                conta = Conta.objects.get(id=conta_id)

                # Verifica se a natureza da conta influencia o tipo
                if conta.natureza == 'devedora':
                    tipo = 'debito'
                    total_debito += valor
                else:
                    tipo = 'credito'
                    total_credito += valor

                itens.append({
                    'conta': conta,
                    'descricao': descricao,
                    'valor': valor,
                    'tipo': tipo,
                    'data': data_lanc
                })

            with transaction.atomic():
                descricao_geral = itens[0]['descricao'] if itens else ''
                data = itens[0]['data'] if itens else None
                lancamento = Lancamento.objects.create(descricao=descricao_geral, data=data)

                for item in itens:
                    lancamento.itens.create(
                        conta=item['conta'],
                        tipo=item['tipo'],
                        valor=item['valor']
                    )

            return JsonResponse({'detail': 'Lançamentos registrados com sucesso!'})

        except Exception as e:
            return JsonResponse({'detail': str(e)}, status=400)
    
    return JsonResponse({'detail': 'Método não permitido'}, status=405)

@login_required
def perfil(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('perfil')

    else:
        user_form = UserForm(instance=request.user)
        profile_form = ProfileForm(instance=request.user.profile)

    context = {
        'user_form': user_form,
        'profile_form': profile_form
    }
    return render(request, 'home/perfil.html', context)

def editar_perfil(request):
    user = request.user
    profile = user.profile

    if request.method == 'POST':
        # Dados do usuário
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')

        # Dados do perfil
        bio = request.POST.get('bio')
        avatar = request.FILES.get('avatar')

        # Atualiza usuário
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.save()

        # Atualiza perfil
        profile.bio = bio
        if avatar:
            profile.avatar = avatar
        profile.save()

        messages.success(request, 'Perfil atualizado com sucesso!')
        return redirect('perfil')

    return render(request, 'home/editar_perfil.html')

@require_GET
def contas_api(request):
    contas = Conta.objects.all().values('id', 'codigo', 'nome')
    contas_list = list(contas)
    return JsonResponse(contas_list, safe=False)
