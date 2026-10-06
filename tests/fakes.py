"""Fakes de LLM compartilhados pelos testes (código só de teste)."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class FakeChat(BaseChatModel):
    """LLM de teste: devolve `respostas` em ordem e conta chamadas.

    `respostas` também aceita uma Exception, que é lançada em todas as
    chamadas (simula rede fora / cota esgotada).
    """

    respostas: object = None
    chamadas: int = 0
    model_name: str = "fake"

    @property
    def _llm_type(self) -> str:
        return "fake"

    def _gerar(self, texto: str) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=texto))])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.chamadas += 1
        if isinstance(self.respostas, Exception):
            raise self.respostas
        if isinstance(self.respostas, list) and len(self.respostas) > 1:
            return self._gerar(self.respostas.pop(0))
        return self._gerar(self.respostas[0])
