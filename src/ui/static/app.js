"use strict";

// Todo texto vindo dos arquivos entra na página via textContent, nunca como HTML.

const el = (id) => document.getElementById(id);

// Resultado exibido no painel (usado pelo botão "Baixar resultado").
let resultadoAberto = null;

function criar(tag, atributos = {}, texto = null) {
  const no = document.createElement(tag);
  for (const [chave, valor] of Object.entries(atributos)) {
    if (chave === "classe") no.className = valor;
    else no.setAttribute(chave, valor);
  }
  if (texto !== null) no.textContent = texto;
  return no;
}

function api() {
  return window.pywebview.api;
}

// ---------------------------------------------------------------- mensagens

function mostrarMensagem(texto, tipo, alvo = "mensagem") {
  const caixa = el(alvo);
  caixa.textContent = texto;
  caixa.className = "mensagem " + tipo;
  caixa.hidden = false;
}

function limparMensagem() {
  el("mensagem").hidden = true;
  el("modal-mensagem").hidden = true;
}

// ------------------------------------------------------------------ valores

// Valores chegam como texto com duas casas ("1234.50"); nada de float.
function emCentavos(texto) {
  const negativo = texto.startsWith("-");
  const [inteiro, decimal = "00"] = texto.replace("-", "").split(".");
  const centavos = parseInt(inteiro, 10) * 100 + parseInt(decimal.padEnd(2, "0"), 10);
  return negativo ? -centavos : centavos;
}

function formatarCentavos(centavos) {
  const sinal = centavos < 0 ? "-" : "";
  const absoluto = Math.abs(centavos);
  const inteiro = Math.floor(absoluto / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const resto = String(absoluto % 100).padStart(2, "0");
  return `${sinal}R$ ${inteiro},${resto}`;
}

function formatarData(iso) {
  const [ano, mes, dia] = iso.split("-");
  return `${dia}/${mes}/${ano}`;
}

function classeDoStatus(status) {
  if (status === "aprovado") return "aprovado";
  if (status === "parcial") return "parcial";
  return "rejeitado";
}

// -------------------------------------------------------------------- lista

async function carregarLista() {
  const resposta = await api().listar_colaboradores_competencias();
  if (!resposta.ok) {
    mostrarMensagem(resposta.erro, "erro");
    return;
  }
  desenharLista(resposta.colaboradores);
}

function desenharLista(colaboradores) {
  const lista = el("lista");
  lista.replaceChildren();
  el("vazio").hidden = colaboradores.length > 0;
  for (const colaborador of colaboradores) {
    lista.appendChild(desenharColaborador(colaborador));
  }
}

function desenharColaborador(colaborador) {
  const secao = criar("section", { classe: "colaborador" });
  const cabecalho = criar("header");
  cabecalho.appendChild(criar("h2", {}, colaborador.nome));
  cabecalho.appendChild(criar("span", { classe: "id" }, colaborador.id));
  secao.appendChild(cabecalho);

  const tabela = criar("table");
  const cab = criar("thead");
  const linhaCab = criar("tr");
  for (const rotulo of ["Competência", "Centro de custo", "Despesas", "Situação", "Ações"]) {
    linhaCab.appendChild(criar("th", { scope: "col" }, rotulo));
  }
  cab.appendChild(linhaCab);
  tabela.appendChild(cab);

  const corpo = criar("tbody");
  for (const competencia of colaborador.competencias) {
    corpo.appendChild(desenharCompetencia(colaborador, competencia));
  }
  tabela.appendChild(corpo);
  secao.appendChild(tabela);
  return secao;
}

function desenharCompetencia(colaborador, competencia) {
  const linha = criar("tr");
  linha.appendChild(criar("td", {}, competencia.competencia));
  linha.appendChild(criar("td", {}, competencia.centro_custo));
  linha.appendChild(
    criar("td", {}, competencia.total_despesas === null ? "—" : String(competencia.total_despesas))
  );

  const situacao = criar("td");
  if (competencia.corrompido) {
    situacao.appendChild(criar("span", { classe: "selo corrompido" }, "Arquivo com problema"));
    situacao.appendChild(criar("span", { classe: "erro-detalhe" }, competencia.erro || ""));
  } else if (competencia.validado) {
    situacao.appendChild(criar("span", { classe: "selo validado" }, "Validado"));
  } else {
    situacao.appendChild(criar("span", { classe: "selo pendente" }, "Pendente de validação"));
  }
  linha.appendChild(situacao);

  const acoes = criar("td", { classe: "acoes" });
  const validar = criar("button", { type: "button", classe: "primario" }, "Validar");
  // Competência validada nunca volta a ser validada (plan.md 4.3).
  validar.disabled = competencia.validado || competencia.corrompido;
  validar.addEventListener("click", () => validarCompetencia(colaborador, competencia));
  const resultado = criar("button", { type: "button", classe: "secundario" }, "Resultado");
  resultado.disabled = !competencia.tem_resultado;
  resultado.addEventListener("click", () => abrirResultado(colaborador, competencia));
  acoes.append(validar, resultado);
  linha.appendChild(acoes);
  return linha;
}

// ------------------------------------------------------------------- ações

async function avaliarReembolso() {
  limparMensagem();
  const escolha = await api().selecionar_arquivo();
  if (!escolha.ok) {
    mostrarMensagem(escolha.erro, "erro");
    return;
  }
  if (!escolha.caminho) return; // usuário cancelou
  const resposta = await api().avaliar_reembolso(escolha.caminho);
  mostrarMensagem(resposta.ok ? resposta.mensagem : resposta.erro, resposta.ok ? "sucesso" : "erro");
  await carregarLista();
}

async function validarCompetencia(colaborador, competencia) {
  const confirmado = window.confirm(
    `Validar a competência ${competencia.competencia} de ${colaborador.nome}?\n` +
      "Depois de validada, ela não poderá ser alterada nem validada novamente."
  );
  if (!confirmado) return;
  limparMensagem();
  const resposta = await api().validar_competencia(
    colaborador.id,
    competencia.centro_custo,
    competencia.competencia
  );
  mostrarMensagem(resposta.ok ? resposta.mensagem : resposta.erro, resposta.ok ? "sucesso" : "erro");
  await carregarLista();
}

// ------------------------------------------------------------ resultado

async function abrirResultado(colaborador, competencia) {
  limparMensagem();
  const resposta = await api().obter_resultado(
    colaborador.id,
    competencia.centro_custo,
    competencia.competencia
  );
  if (!resposta.ok) {
    mostrarMensagem(resposta.erro, "erro");
    return;
  }
  resultadoAberto = { colaborador, competencia };
  desenharResultado(colaborador, competencia, resposta.resultado);
  el("modal-resultado").showModal();
}

// Pede o destino ao usuário e grava ali uma cópia do resultado aberto.
async function baixarResultado() {
  if (!resultadoAberto) return;
  const botao = el("btn-baixar");
  botao.disabled = true;
  limparMensagem();
  try {
    const { colaborador, competencia } = resultadoAberto;
    const resposta = await api().baixar_resultado(
      colaborador.id,
      competencia.centro_custo,
      competencia.competencia
    );
    const tipo = !resposta.ok ? "erro" : resposta.cancelado ? "" : "sucesso";
    mostrarMensagem(resposta.ok ? resposta.mensagem : resposta.erro, tipo, "modal-mensagem");
  } finally {
    botao.disabled = false;
  }
}

function desenharResultado(colaborador, competencia, resultado) {
  el("modal-titulo").textContent =
    `Resultado — ${colaborador.nome} — ${competencia.competencia}`;

  const itens = resultado.historico_despesas.flatMap((h) => h.despesas);
  const contagem = { aprovado: 0, parcial: 0, rejeitado: 0 };
  let total = 0;
  for (const item of itens) {
    contagem[classeDoStatus(item.status_item)] += 1;
    total += emCentavos(item.valor_reembolsado);
  }
  el("modal-resumo").textContent =
    `Total reembolsado: ${formatarCentavos(total)} · ` +
    `${contagem.aprovado} aprovada(s), ${contagem.parcial} parcial(is), ` +
    `${contagem.rejeitado} rejeitada(s) de ${itens.length} despesa(s).`;

  const corpo = el("tabela-itens").querySelector("tbody");
  corpo.replaceChildren();
  for (const item of itens) {
    const linha = criar("tr");
    linha.appendChild(criar("td", {}, formatarData(item.data)));
    linha.appendChild(criar("td", {}, item.descricao));
    linha.appendChild(criar("td", {}, item.fornecedor));
    const status = criar("td");
    status.appendChild(
      criar("span", { classe: "selo " + classeDoStatus(item.status_item) }, item.status_item)
    );
    linha.appendChild(status);
    linha.appendChild(criar("td", { classe: "num" }, formatarCentavos(emCentavos(item.valor_reembolsado))));
    linha.appendChild(criar("td", {}, item.justificativa));
    corpo.appendChild(linha);
  }
}

// -------------------------------------------------------------- inicialização

function iniciar() {
  el("btn-avaliar").addEventListener("click", avaliarReembolso);
  el("btn-atualizar").addEventListener("click", () => {
    limparMensagem();
    carregarLista();
  });
  el("btn-baixar").addEventListener("click", baixarResultado);
  el("btn-fechar").addEventListener("click", () => el("modal-resultado").close());
  carregarLista();
}

// A ponte `window.pywebview.api` só existe depois deste evento.
window.addEventListener("pywebviewready", iniciar);
