from django.db import models
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.contrib.auth.models import User

class Conta(models.Model):
    TIPO_CHOICES = [
        ('ativo', 'Ativo'),
        ('passivo', 'Passivo'),
        ('despesa', 'Despesa'),
        ('patrimonio_liquido', 'Patrimônio Líquido'),
        ('custo', 'Custo'),            # novo
        ('receita', 'Receita'),          # novo
    ]

    NATUREZA_CHOICES = [
        ('devedora', 'Devedora'),
        ('credora', 'Credora'),
    ]

    nome = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    natureza = models.CharField(max_length=10, choices=NATUREZA_CHOICES)
    codigo = models.CharField(max_length=20, unique=True)
    is_are = models.BooleanField(default=False)

    @property
    def saldo(self):
        debitos = self.itens_lancamento.filter(tipo='debito').aggregate(total=Sum('valor'))['total'] or 0
        creditos = self.itens_lancamento.filter(tipo='credito').aggregate(total=Sum('valor'))['total'] or 0

        if self.natureza == 'devedora':
            return debitos - creditos
        else:
            return creditos - debitos
        
    def __str__(self):
        return f"{self.codigo} - {self.nome} ({self.tipo})"


class Lancamento(models.Model):
    descricao = models.CharField(max_length=255)
    data = models.DateField()
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lançamento {self.id} - {self.descricao} em {self.data}"

    def total_debitos(self):
        return sum(item.valor for item in self.itens.all() if item.tipo == 'debito')

    def total_creditos(self):
        return sum(item.valor for item in self.itens.all() if item.tipo == 'credito')


class LancamentoItem(models.Model):
    TIPO_CHOICES = [
        ('debito', 'Débito'),
        ('credito', 'Crédito'),
    ]

    lancamento = models.ForeignKey(Lancamento, on_delete=models.CASCADE, related_name='itens')
    conta = models.ForeignKey(Conta, on_delete=models.PROTECT, related_name='itens_lancamento')
    tipo = models.CharField(max_length=7, choices=TIPO_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=2)

    def clean(self):
        # Removido a restrição sintética pois você não usa mais esse campo
        pass

    def __str__(self):
        return f"{self.tipo.capitalize()}: {self.valor} na conta {self.conta.codigo} - {self.conta.nome}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True, null=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    data_nascimento = models.DateField(blank=True, null=True)

    def __str__(self):
        return f'Perfil de {self.user.username}'
