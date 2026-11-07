"""
Módulo individual: MULHERES (IBGE)
Indicador sugerido: % de mulheres na população residente, por UF (Censo 2022 - SIDRA/IBGE).
Alternativas: razão de sexo, % de domicílios com mulher responsável, rendimento médio das mulheres.

Uso isolado:   streamlit run modulo_mulheres.py
Uso no painel: from modulo_mulheres import render; render()
"""
import io
import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

TITULO = "Mulheres"
PERGUNTA = ("Como a proporção de mulheres varia entre os estados, e quais territórios "
            "fogem do padrão nacional?")


# ----------------------------- 1) ETL -----------------------------
@st.cache_data(show_spinner=False)
def ler_arquivo(conteudo: bytes, nome: str) -> pd.DataFrame:
    """Lê CSV/XLSX (inclusive exportações do SIDRA, que têm linhas de cabeçalho extras)."""
    buf = io.BytesIO(conteudo)
    if nome.lower().endswith((".xlsx", ".xls")):
        bruto = pd.read_excel(buf, header=None)
    else:
        try:
            bruto = pd.read_csv(buf, header=None, sep=None, engine="python", encoding="utf-8")
        except UnicodeDecodeError:
            buf.seek(0)
            bruto = pd.read_csv(buf, header=None, sep=None, engine="python", encoding="latin-1")
    # Detecta a linha de cabeçalho: a primeira com >= 2 células preenchidas e texto
    for i in range(min(15, len(bruto))):
        linha = bruto.iloc[i]
        if linha.notna().sum() >= 2 and linha.map(lambda x: isinstance(x, str)).sum() >= 2:
            df = bruto.iloc[i + 1:].copy()
            df.columns = [str(c).strip() for c in linha]
            return df.reset_index(drop=True)
    return bruto


def tratar(df: pd.DataFrame, col_territorio: str, col_valor: str) -> pd.DataFrame:
    """Limpa nomes, converte valores numéricos (vírgula decimal, '-', '...', 'X') e remove nulos/duplicados."""
    out = df[[col_territorio, col_valor]].copy()
    out.columns = ["Território", "Valor"]
    out["Território"] = out["Território"].astype(str).str.strip()
    v = out["Valor"].astype(str).str.strip().replace({"-": np.nan, "..": np.nan, "...": np.nan, "X": np.nan, "nan": np.nan})
    # trata "1.234,56" (pt-BR) e "1234.56"
    v = v.str.replace(r"\.(?=\d{3}(\D|$))", "", regex=True).str.replace(",", ".", regex=False)
    out["Valor"] = pd.to_numeric(v, errors="coerce")
    out = out.dropna().drop_duplicates("Território")
    out = out[~out["Território"].str.lower().isin(["brasil", "total"])]
    return out.reset_index(drop=True)


def dados_demo() -> pd.DataFrame:
    """DADOS FICTÍCIOS apenas para testar o app. Substitua pela base real do IBGE."""
    ufs = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB",
           "PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]
    rng = np.random.default_rng(42)
    vals = rng.normal(51.5, 0.7, len(ufs)).round(1)
    vals[ufs.index("RR")] = 49.0  # outlier de demonstração
    return pd.DataFrame({"Território": ufs, "Valor": vals})


# ------------------------- 2) ESTATÍSTICAS -------------------------
def estatisticas(s: pd.Series) -> dict:
    q1, q2, q3 = s.quantile([.25, .5, .75])
    iqr = q3 - q1
    li, ls = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    moda = s.round(1).mode()
    return dict(
        n=len(s), media=s.mean(), mediana=s.median(),
        moda=moda.iloc[0] if len(moda) else np.nan, moda_unica=len(moda) == 1,
        q1=q1, q2=q2, q3=q3, iqr=iqr, minimo=s.min(), maximo=s.max(),
        amplitude=s.max() - s.min(), desvio=s.std(ddof=1),
        cv=s.std(ddof=1) / s.mean() * 100 if s.mean() else np.nan,
        lim_inf=li, lim_sup=ls, assimetria=s.skew(),
    )


def interpretar(e: dict) -> str:
    if abs(e["media"] - e["mediana"]) < 0.05 * e["mediana"]:
        forma = "aproximadamente simétrica (média ≈ mediana)"
    elif e["media"] > e["mediana"]:
        forma = "assimétrica à direita (média > mediana): poucos territórios altos puxam a média para cima"
    else:
        forma = "assimétrica à esquerda (média < mediana): poucos territórios baixos puxam a média para baixo"
    hom = "alta heterogeneidade" if e["cv"] > 30 else "heterogeneidade moderada" if e["cv"] > 15 else "relativa homogeneidade"
    return f"A distribuição é {forma}. O coeficiente de variação de {e['cv']:.1f}% indica {hom} entre os territórios."


# ----------------------------- 3) APP -----------------------------
def render():
    st.header(f"👩 {TITULO}")
    st.caption(f"**Pergunta de negócio:** {PERGUNTA}")

    with st.sidebar:
        st.subheader(f"Filtros · {TITULO}")
        arq = st.file_uploader("Base IBGE tratada (CSV/XLSX)", type=["csv", "xlsx", "xls"], key="mu_up")
        usar_demo = st.checkbox("Usar dados de demonstração (fictícios)", value=arq is None, key="mu_demo")

    # --- Ingestão ---
    try:
        if arq is not None:
            bruto = ler_arquivo(arq.getvalue(), arq.name)
            cols = list(bruto.columns)
            with st.sidebar:
                c_t = st.selectbox("Coluna do território", cols, index=0, key="mu_ct")
                num = [c for c in cols if pd.to_numeric(bruto[c].astype(str).str.replace(",", "."), errors="coerce").notna().mean() > .6 and c != c_t]
                c_v = st.selectbox("Coluna do valor", num or cols, index=len(num) - 1 if num else 0, key="mu_cv")
            df = tratar(bruto, c_t, c_v)
        elif usar_demo:
            st.warning("Exibindo **dados fictícios de demonstração**. Faça upload da base real do IBGE.")
            df = dados_demo()
        else:
            st.info("Envie um arquivo CSV/XLSX na barra lateral para começar.")
            return
    except Exception as ex:
        st.error(f"Não foi possível processar o arquivo: {ex}")
        return

    if df.empty or len(df) < 4:
        st.error("Poucos dados válidos após o tratamento (mínimo 4 territórios).")
        return

    # --- Filtros ---
    with st.sidebar:
        lo, hi = float(df.Valor.min()), float(df.Valor.max())
        faixa = st.slider("Faixa de valores (%)", lo, hi, (lo, hi), key="mu_faixa")
        sel = st.multiselect("Territórios", sorted(df["Território"]), default=sorted(df["Território"]), key="mu_sel")
        mostrar_out = st.checkbox("Destacar outliers", True, key="mu_out")
    f = df[df.Valor.between(*faixa) & df["Território"].isin(sel)].reset_index(drop=True)
    if len(f) < 4:
        st.warning("Os filtros deixaram menos de 4 territórios. Amplie a seleção.")
        return

    e = estatisticas(f.Valor)
    f["Outlier"] = (f.Valor < e["lim_inf"]) | (f.Valor > e["lim_sup"])

    # --- KPIs ---
    k = st.columns(4)
    k[0].metric("Média", f"{e['media']:.2f}")
    k[1].metric("Mediana", f"{e['mediana']:.2f}")
    k[2].metric("Desvio padrão", f"{e['desvio']:.2f}")
    k[3].metric("Nº de outliers", int(f.Outlier.sum()))

    t1, t2, t3, t4 = st.tabs(["📊 Estatísticas", "📈 Gráficos", "🚨 Outliers", "📰 Contexto"])

    with t1:
        tab = pd.DataFrame({
            "Métrica": ["Média", "Mediana", "Moda (1 casa)", "Q1", "Q2", "Q3", "IQR", "Mínimo", "Máximo",
                        "Amplitude", "Desvio padrão", "Coef. de variação (%)"],
            "Valor": [e["media"], e["mediana"], e["moda"], e["q1"], e["q2"], e["q3"], e["iqr"],
                      e["minimo"], e["maximo"], e["amplitude"], e["desvio"], e["cv"]]})
        st.dataframe(tab.round(2), hide_index=True, use_container_width=True)
        if not e["moda_unica"]:
            st.caption("Há mais de uma moda; exibida a menor. Em dados contínuos a moda é pouco informativa.")
        st.info(interpretar(e))
        st.download_button("⬇️ Baixar base tratada (CSV)", f.to_csv(index=False).encode("utf-8"),
                           "mulheres_tratado.csv", "text/csv")

    with t2:
        c1, c2 = st.columns(2)
        fig_box = px.box(f, y="Valor", points="all", hover_name="Território",
                         title="Boxplot do indicador", labels={"Valor": "% de mulheres"})
        c1.plotly_chart(fig_box, use_container_width=True)
        ordem = f.sort_values("Valor", ascending=False)
        fig_bar = px.bar(ordem, x="Território", y="Valor", color="Outlier" if mostrar_out else None,
                         title="Ranking por território", labels={"Valor": "% de mulheres"})
        fig_bar.add_hline(y=e["media"], line_dash="dash", annotation_text="média")
        fig_bar.add_hline(y=e["mediana"], line_dash="dot", annotation_text="mediana")
        c2.plotly_chart(fig_bar, use_container_width=True)
        st.plotly_chart(px.histogram(f, x="Valor", nbins=10, title="Histograma"), use_container_width=True)

    with t3:
        st.markdown(f"**Regra 1,5×IQR:** limite inferior = {e['lim_inf']:.2f} · limite superior = {e['lim_sup']:.2f}")
        out = f[f.Outlier]
        if out.empty:
            st.success("Nenhum outlier identificado nos dados filtrados.")
        else:
            st.dataframe(out.round(2), hide_index=True, use_container_width=True)
            sem = f[~f.Outlier].Valor
            st.write(f"Média com outliers: **{e['media']:.2f}** · sem outliers: **{sem.mean():.2f}** "
                     f"(diferença de {e['media'] - sem.mean():+.2f} p.p.).")
            st.caption("Justificativa sugerida: explique por que esses territórios fogem do padrão "
                       "(ex.: migração masculina para trabalho, fronteira/garimpo, urbanização, expectativa de vida).")

    with t4:
        st.subheader("Notícias e imagens do tema")
        st.caption("Edite as listas abaixo com as fontes reais escolhidas pelo grupo.")
        noticias = [  # (título, fonte, url)
            ("Preencha com uma notícia sobre mulheres no Brasil (demografia, trabalho, renda)", "Agência IBGE Notícias", "https://agenciadenoticias.ibge.gov.br/"),
            ("Preencha com uma notícia sobre desigualdade de gênero", "IBGE - Estatísticas de Gênero", "https://www.ibge.gov.br/estatisticas/multidominio/genero.html"),
        ]
        for t, fonte, url in noticias:
            st.markdown(f"- [{t}]({url}) — *{fonte}*")
        img = st.text_input("URL de imagem ilustrativa (opcional)", key="mu_img")
        if img:
            st.image(img, use_container_width=True)


if __name__ == "__main__":
    st.set_page_config(page_title=TITULO, layout="wide")
    render()
