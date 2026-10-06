from chat_usuario import AMOSTRA, parsear_ground, resolver_caso


def test_parsear_ground_percentual():
    texto = "=" * 78 + "\nresposta do arquivista\n" \
            "ground: 89% (8/9 citações no contexto)\n" + "=" * 78
    assert parsear_ground(texto) == 0.89


def test_parsear_ground_sem_citacoes_e_sem_resposta():
    assert parsear_ground("ground: n/a (resposta sem citações)") is None
    assert parsear_ground("Não consegui gerar uma resposta estável agora") is None
    assert parsear_ground("") is None


def test_resolver_caso_por_prefixo_numerico():
    casos = [{"id": "42_cd_heroica", "consulta": "a"},
             {"id": "01_condicao_caido", "consulta": "b"}]
    assert resolver_caso(casos, "42")["id"] == "42_cd_heroica"
    assert resolver_caso(casos, "01_condicao_caido")["id"] == "01_condicao_caido"
    assert resolver_caso(casos, "99") is None


def test_amostra_tem_28_prefixos_unicos():
    assert len(AMOSTRA) == 28 == len(set(AMOSTRA))
    assert "42" in AMOSTRA
