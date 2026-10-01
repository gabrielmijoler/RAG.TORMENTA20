#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";

const args = process.argv.slice(2);

function pegar(nome, padrao) {
  const i = args.indexOf(nome);
  return i >= 0 && args[i + 1] !== undefined ? args[i + 1] : padrao;
}

const DIR = path.resolve(
  pegar("--dir", path.join(process.cwd(), "..", "aTormenta", "data")),
);
const PULAR = new Set(["search-index.ts"]);

const avisos = [];

function fim_da_string(src, ini) {
  const aspa = src[ini];
  let i = ini + 1;
  while (i < src.length) {
    const c = src[i];
    if (c === "\\") {
      i += 2;
      continue;
    }
    if (c === aspa) return i + 1;
    if (aspa === "`" && c === "$" && src[i + 1] === "{") {
      const f = fim_do_bloco(src, i + 1, "{", "}");
      i = f < 0 ? src.length : f + 1;
      continue;
    }
    i++;
  }
  return src.length;
}

function fim_do_bloco(src, ini, abre, fecha) {
  let prof = 0;
  let i = ini;
  while (i < src.length) {
    const c = src[i];
    if (c === "/" && src[i + 1] === "/") {
      const f = src.indexOf("\n", i);
      if (f < 0) return -1;
      i = f + 1;
      continue;
    }
    if (c === "/" && src[i + 1] === "*") {
      const f = src.indexOf("*/", i + 2);
      if (f < 0) return -1;
      i = f + 2;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") {
      i = fim_da_string(src, i);
      continue;
    }
    if (c === abre) prof++;
    else if (c === fecha) {
      prof--;
      if (prof === 0) return i;
    }
    i++;
  }
  return -1;
}

function pular_trivia(src, ini, fim) {
  let p = ini;
  for (;;) {
    while (p < fim && /\s/.test(src[p])) p++;
    if (src[p] === "/" && src[p + 1] === "/") {
      const f = src.indexOf("\n", p);
      p = f < 0 || f > fim ? fim : f + 1;
      continue;
    }
    if (src[p] === "/" && src[p + 1] === "*") {
      const f = src.indexOf("*/", p + 2);
      p = f < 0 || f > fim ? fim : f + 2;
      continue;
    }
    return p;
  }
}

function limites_elementos(src, ini, fim) {
  const trechos = [];
  let inicio = pular_trivia(src, ini + 1, fim);
  let prof = 0;
  let i = inicio;
  while (i < fim) {
    const c = src[i];
    if (c === "/" && src[i + 1] === "/") {
      const f = src.indexOf("\n", i);
      i = f < 0 || f > fim ? fim : f + 1;
      continue;
    }
    if (c === "/" && src[i + 1] === "*") {
      const f = src.indexOf("*/", i + 2);
      i = f < 0 || f > fim ? fim : f + 2;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") {
      i = fim_da_string(src, i);
      continue;
    }
    if (c === "(" || c === "[" || c === "{") prof++;
    else if (c === ")" || c === "]" || c === "}") prof--;
    else if (c === "," && prof === 0) {
      if (inicio < i) trechos.push([inicio, i]);
      inicio = pular_trivia(src, i + 1, fim);
      i = inicio;
      continue;
    }
    i++;
  }
  if (inicio < fim) trechos.push([inicio, fim]);
  return trechos;
}

function mapa_regioes(src) {
  const marcas = [];
  const re = /^[ \t]*\/\/[ \t]*#(region|endregion)[ \t]*(.*)$/gm;
  let m;
  while ((m = re.exec(src))) {
    marcas.push({
      pos: m.index,
      fim: m.index + m[0].length,
      tipo: m[1],
      nome: m[2].trim(),
    });
  }
  return marcas;
}

function regiao_na(marcas, pos) {
  let atual = null;
  for (const marca of marcas) {
    if (marca.pos > pos) break;
    if (marca.pos <= pos && marca.fim >= pos) return atual;
    atual = marca.tipo === "region" ? marca.nome || null : null;
  }
  return atual;
}

function achar_exports(src) {
  const achados = [];
  const re = /^export\s+const\s+([A-Za-z_$][\w$]*)\s*(?::[^=]*?)?=\s*/gm;
  let m;
  while ((m = re.exec(src))) {
    achados.push({
      nome: m[1],
      ini: m.index,
      valor_ini: re.lastIndex,
      declaracao: m[0],
    });
  }
  for (let k = 0; k < achados.length; k++) {
    const item = achados[k];
    item.tipo = /:\s*([^=]+?)\s*=\s*$/.exec(item.declaracao)?.[1] ?? "";
    item.fim =
      k + 1 < achados.length
        ? achados[k + 1].ini
        : src.length;
    item.valor_fim = limite_valor(src, item.valor_ini, item.fim);
  }
  return achados;
}

function limite_valor(src, ini, fim) {
  let i = ini;
  while (i < fim && /\s/.test(src[i])) i++;
  const c = src[i];
  if (c === "[" || c === "{") {
    const f = fim_do_bloco(src, i, c, c === "[" ? "]" : "}");
    return f < 0 ? fim : f + 1;
  }
  if (c === '"' || c === "'" || c === "`") return fim_da_string(src, i);
  let j = i;
  while (j < fim && src[j] !== ";" && src[j] !== "\n") j++;
  return j;
}

const RE_BLOCOS =
  /("(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|`(?:[^`\\]|\\.)*`|\/\/[^\n]*|\/\*[\s\S]*?\*\/)/g;

function mascarar_assertions(texto) {
  return texto
    .split(RE_BLOCOS)
    .map((pedaco, k) => (k % 2 === 1 ? pedaco : mascarar_fora(pedaco)))
    .join("");
}

function mascarar_fora(texto) {
  return texto.replace(
    /(\s)as\s+([A-Za-z_$][\w$]*)(\s*[,}\])\n])/g,
    (bruto, espaco, tipo, fim) => espaco + " ".repeat(2 + tipo.length) + fim,
  );
}

const GLOBAIS = new Set([
  "undefined", "NaN", "Infinity", "globalThis", "Object", "Array", "String",
  "Number", "Boolean", "Symbol", "Math", "JSON", "Date", "RegExp",
  "parseInt", "parseFloat", "isNaN", "isFinite",
]);

function contexto_de(registroGlobal, locais) {
  const base = { ...registroGlobal, ...locais };
  return new Proxy(base, {
    has: (_alvo, chave) => true,
    get: (alvo, chave) => {
      if (typeof chave === "symbol") return undefined;
      if (chave in alvo) return alvo[chave];
      if (GLOBAIS.has(chave)) return undefined;
      return { __identificador: String(chave) };
    },
  });
}

function sanificar(valor) {
  if (Array.isArray(valor)) return valor.map(sanificar);
  if (valor && typeof valor === "object") {
    if (typeof valor.__identificador === "string") return valor.__identificador;
    const saida = {};
    for (const [chave, item] of Object.entries(valor)) saida[chave] = sanificar(item);
    return saida;
  }
  return valor;
}

function avaliar(texto, contexto) {
  return vm.runInNewContext(`(${texto})`, contexto, {
    timeout: 20000,
  });
}

function para_registros(valor) {
  if (Array.isArray(valor)) {
    return valor.map((item) =>
      item !== null && typeof item === "object"
        ? item
        : { __valor: item },
    );
  }
  return [{ __valor: valor }];
}

function valor_de(expr, item, indice, params) {
  const limpo = expr.trim();
  if (limpo === "") return "";
  if (/^".*"$|^'.*'$/.test(limpo)) return limpo.slice(1, -1);
  if (limpo === params[0] || limpo === params[1]) {
    if (item && typeof item === "object") return item.name ?? item.title ?? "";
    return indice;
  }
  if (params[0] && limpo.startsWith(params[0] + ".")) {
    return formatar(ler_caminho(item, limpo.slice(params[0].length + 1)));
  }
  if (params[1] && limpo === params[1]) return indice;
  return "";
}

function ler_caminho(alvo, caminho) {
  let atual = alvo;
  for (const parte of caminho.split(".")) {
    if (atual === null || atual === undefined) return "";
    atual = atual[parte];
  }
  return atual;
}

function formatar(valor) {
  if (valor === null || valor === undefined) return "";
  if (Array.isArray(valor)) return valor.map(formatar).filter(Boolean).join(", ");
  if (typeof valor === "object") return valor.name ?? valor.title ?? "";
  return String(valor);
}

const MAPEAMENTO_TAGS = {
  p: (f) => (f ? "\n\n" : ""),
  div: () => "\n",
  li: (f) => (f ? "" : "\n- "),
  ul: () => "\n",
  ol: () => "\n",
  br: () => "\n",
  h3: (f) => (f ? "\n" : "\n\n### "),
  h4: (f) => (f ? "\n" : "\n\n### "),
  h5: (f) => (f ? "\n" : "\n\n#### "),
  strong: () => "**",
  b: () => "**",
  em: () => "*",
  i: () => "*",
  span: () => "",
  u: () => "",
  small: () => "",
  a: () => "",
  blockquote: (f) => (f ? "\n" : "\n\n> "),
  table: () => "\n",
  thead: () => "\n",
  tbody: () => "\n",
  tr: () => "\n",
  td: () => " | ",
  th: () => " | ",
  figure: () => "\n",
  figcaption: () => "\n",
  img: () => "",
  input: () => "",
  hr: () => "\n",
};

function tags_para_md(texto) {
  const re = /<\/?([A-Za-z][\w-]*)((?:[^>"']|"[^"]*"|'[^']*')*)>/g;
  return texto.replace(re, (bruto, nome, attrs) => {
    const fechando = bruto.startsWith("</");
    const autoFechando = /\/\s*$/.test(attrs);
    const mae = MAPEAMENTO_TAGS[nome.toLowerCase()];
    if (!mae) return "";
    if (autoFechando && nome.toLowerCase() === "br") return "\n";
    if (autoFechando && nome.toLowerCase() === "hr") return "\n";
    if (autoFechando) return "";
    return mae(fechando);
  });
}

function limpar_expressoes(texto, dados) {
  let saida = "";
  let i = 0;
  while (i < texto.length) {
    const c = texto[i];
    if (c === "{") {
      const f = fim_do_bloco(texto, i, "{", "}");
      if (f < 0) {
        saida += c;
        i++;
        continue;
      }
      const bruto = texto.slice(i + 1, f).trim();
      if (/^\/\*/.test(bruto)) {
        i = f + 1;
        continue;
      }
      if (/^[A-Za-z_$][\w$]*$/.test(bruto) && bruto in dados) {
        saida += formatar(dados[bruto]);
      } else if (/^".*"$|^'.*'$/.test(bruto)) {
        saida += bruto.slice(1, -1);
      } else if (/^[\w$.[\]"' ]+$/.test(bruto) && !/[()=<>]/.test(bruto)) {
        saida += "";
      }
      i = f + 1;
      continue;
    }
    saida += c;
    i++;
  }
  return saida;
}

function substituir_componentes(texto, dados) {
  return texto.replace(
    /<([A-Z][\w]*)\s+([^>]*?)\/>/g,
    (bruto, nome, attrs) => {
      const ref = /data=\{([A-Za-z_$][\w$]*)\}/.exec(attrs)?.[1];
      const extra = /footnote=\{([A-Za-z_$][\w$]*)\}/.exec(attrs)?.[1];
      if (!ref || !(ref in dados)) return "";
      const dadosTabela = formatar_tabela(dados[ref]);
      const nota = extra && extra in dados ? formatar(dados[extra]) : "";
      return `${dadosTabela}${nota ? `\n${nota}` : ""}`;
    },
  );
}

function formatar_tabela(valor) {
  if (!Array.isArray(valor)) return formatar(valor);
  return valor
    .map((linha) => {
      if (linha === null || typeof linha !== "object") return `- ${formatar(linha)}`;
      return `- ${Object.values(linha).map(formatar).filter(Boolean).join(" — ")}`;
    })
    .filter(Boolean)
    .join("\n");
}

function substituir_maps(texto, dados) {
  const re = /\{\s*([A-Za-z_$][\w$]*)\s*\.map\(\s*\(([^()]*)\)\s*=>\s*\(/g;
  let saida = "";
  let pos = 0;
  let m;
  while ((m = re.exec(texto))) {
    const inicio = m.index;
    const fechaChave = fim_do_bloco(texto, inicio, "{", "}");
    if (fechaChave < 0) continue;
    const abrePar = inicio + m[0].length - 1;
    const fechaPar = fim_do_bloco(texto, abrePar, "(", ")");
    if (fechaPar < 0 || fechaPar > fechaChave) continue;
    const nome = m[1];
    const params = m[2]
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const lista = dados[nome];
    const corpo = texto.slice(abrePar + 1, fechaPar);
    let bloco = "";
    if (Array.isArray(lista)) {
      bloco = lista
        .map((item, indice) => {
          const itemCorpo = corpo.replace(
            /\{([^{}]+)\}/g,
            (_b, expr) => valor_de(expr, item, indice, params),
          );
          return limpar_expressoes(tags_para_md(itemCorpo), dados).trim();
        })
        .filter(Boolean)
        .join("\n");
    }
    saida += texto.slice(pos, inicio) + (bloco ? `\n${bloco}\n` : "");
    pos = fechaChave + 1;
    re.lastIndex = pos;
  }
  return saida + texto.slice(pos);
}

function jsx_para_texto(jsx, dados) {
  let t = jsx.replace(/\{\s*\/\*[\s\S]*?\*\/\s*\}/g, "");
  t = substituir_componentes(t, dados);
  t = substituir_maps(t, dados);
  t = limpar_expressoes(t, dados);
  t = tags_para_md(t);
  return limpar_texto(t);
}

function limpar_texto(texto) {
  return texto
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n[ \t]+/g, "\n")
    .replace(/[ \t]{2,}/g, " ")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/-\n- /g, "\n- ")
    .replace(/^\s+|\s+$/g, "");
}

function extrair_rule_sections(src_array, dados) {
  const marcas = [];
  const re = /\{\s*id:\s*"([^"]+)"\s*,\s*title:\s*"([^"]+)"\s*,/g;
  let m;
  while ((m = re.exec(src_array))) {
    marcas.push({ ini: m.index, id: m[1], title: m[2], corpo: re.lastIndex });
  }
  const registros = [];
  for (let k = 0; k < marcas.length; k++) {
    const fim =
      k + 1 < marcas.length ? marcas[k + 1].ini : src_array.length;
    const corpo = src_array.slice(marcas[k].corpo, fim);
    registros.push({
      id: marcas[k].id,
      title: marcas[k].title,
      content: conteudo_jsx(corpo, dados),
      ...campos_simples(corpo),
    });
  }
  return registros;
}

function conteudo_jsx(corpo, dados) {
  const marca = /content\s*:\s*\(/.exec(corpo);
  if (!marca) return "";
  const abre = marca.index + marca[0].length - 1;
  const terminador = /\n {4}\)\n {2}[}\]]/.exec(corpo.slice(abre));
  let jsx;
  if (terminador) {
    jsx = corpo.slice(abre + 1, abre + 1 + terminador.index);
  } else {
    const f = fim_do_bloco(corpo, abre, "(", ")");
    if (f < 0) return "";
    jsx = corpo.slice(abre + 1, f);
  }
  return jsx_para_texto(jsx, dados);
}

function campos_simples(corpo) {
  const semContent = corpo.replace(/content\s*:\s*\([\s\S]*$/, "");
  const campos = {};
  const re = /(?:^|\n)\s*([A-Za-z_$][\w$]*)\s*:\s*"((?:[^"\\]|\\.)*)"/g;
  let m;
  while ((m = re.exec(semContent))) campos[m[1]] = m[2];
  return campos;
}

const registroGlobal = {};

function processar_arquivo(caminho, dados) {
  const nomeArquivo = path.basename(caminho);
  const src = mascarar_assertions(fs.readFileSync(caminho, "utf8"));
  const marcas = mapa_regioes(src);
  const exports = achar_exports(src);
  const saida = [];

  for (const item of exports) {
    const textoValor = src.slice(item.valor_ini, item.valor_fim);
    const cabeca = textoValor.trimStart().slice(0, 16);
    if (/=>|function/.test(cabeca)) {
      avisos.push(`${nomeArquivo}: export '${item.nome}' nao e literal, pulado`);
      continue;
    }

    let valor;
    try {
      valor = sanificar(avaliar(textoValor, contexto_de(registroGlobal, dados)));
    } catch (erro) {
      if (item.nome === "ruleSections") {
        const registros = extrair_rule_sections(textoValor, {
          ...registroGlobal,
          ...dados,
        });
        const regiao = regiao_na(marcas, item.valor_ini);
        saida.push({
          arquivo: nomeArquivo,
          export: item.nome,
          tipo: item.tipo,
          e_array: true,
          elementos: registros.map((r) => ({ ...r, __regiao: regiao })),
        });
        dados[item.nome] = registros;
        registroGlobal[item.nome] = registros;
        continue;
      }
      avisos.push(`${nomeArquivo}: '${item.nome}' nao avaliou (${erro.message})`);
      continue;
    }

    dados[item.nome] = valor;
    registroGlobal[item.nome] = valor;

    let elementos;
    const primeiro = textoValor.trimStart()[0];
    if (primeiro === "[" && Array.isArray(valor)) {
      const trechos = limites_elementos(
        src,
        src.indexOf("[", item.valor_ini),
        item.valor_fim - 1,
      );
      if (trechos.length === valor.length) {
        elementos = valor.map((item2, k) => {
          const base =
            item2 !== null && typeof item2 === "object" ? item2 : { __valor: item2 };
          return {
            ...base,
            __regiao: regiao_na(marcas, trechos[k][0]),
          };
        });
      } else {
        elementos = para_registros(valor).map((r) => ({
          ...r,
          __regiao: regiao_na(marcas, item.valor_ini),
        }));
        if (trechos.length !== valor.length) {
          avisos.push(
            `${nomeArquivo}: '${item.nome}' ${trechos.length} trechos != ${valor.length} elementos (regioes aproximadas)`,
          );
        }
      }
    } else {
      elementos = para_registros(valor).map((r) => ({
        ...r,
        __regiao: regiao_na(marcas, item.valor_ini),
      }));
    }

    saida.push({
      arquivo: nomeArquivo,
      export: item.nome,
      tipo: item.tipo,
      e_array: Array.isArray(valor),
      elementos,
    });
  }

  return saida;
}

function principal() {
  if (!fs.existsSync(DIR)) {
    console.error(`diretorio nao encontrado: ${DIR}`);
    process.exit(2);
  }
  const arquivos = fs
    .readdirSync(DIR)
    .filter((f) => /\.(ts|tsx)$/.test(f))
    .filter((f) => !PULAR.has(f))
    .sort();

  const exports = [];
  for (const arquivo of arquivos) {
    const dados = {};
    try {
      exports.push(...processar_arquivo(path.join(DIR, arquivo), dados));
    } catch (erro) {
      avisos.push(`${arquivo}: falhou (${erro.message})`);
    }
  }

  const registros = exports.reduce((soma, e) => soma + e.elementos.length, 0);
  const resultado = {
    origem: DIR,
    arquivos: arquivos.length,
    exports: exports.length,
    registros,
    avisos,
    tabelas: exports,
  };
  process.stdout.write(JSON.stringify(resultado));
  process.stderr.write(
    `extracao: ${arquivos.length} arquivos, ${exports.length} exports, ` +
      `${registros} registros, ${avisos.length} avisos\n`,
  );
}

principal();
