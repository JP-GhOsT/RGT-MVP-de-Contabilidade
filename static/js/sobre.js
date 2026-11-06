feather.replace();

function toggleMenu() {
  const menu = document.getElementById("menuLateral");
  const btn = document.getElementById("toggleBtn");
  menu.classList.toggle("hidden");
  btn.classList.toggle("hide");
}

function toggleFerramentas() {
  const submenu = document.getElementById("submenuFerramentas");
  submenu.classList.toggle("mostrar");
}

function alternarTema() {
  const body = document.body;
  const caixaTexto = document.querySelector('.caixa-texto');
  const temaBtn = document.getElementById("temaBtn");

  const isClaro = body.style.backgroundColor === 'var(--cor-fundo-claro)' || body.style.backgroundColor === 'rgb(255, 255, 255)';

  if (isClaro) {
    body.style.backgroundColor = 'var(--cor-fundo-escuro)';
    body.style.color = 'var(--cor-texto-escuro)';
    caixaTexto.style.backgroundColor = 'rgba(30, 30, 30, 0.85)';
    caixaTexto.style.color = '#fff';
    temaBtn.textContent = '🌙';
  } else {
    body.style.backgroundColor = 'var(--cor-fundo-claro)';
    body.style.color = 'var(--cor-texto-claro)';
    caixaTexto.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
    caixaTexto.style.color = '#000';
    temaBtn.textContent = '☀️';
  }
}
