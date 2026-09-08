# src/agent/graph.py
import time
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.router import Router
from nodes.analyzer import AnalyzerNode
from nodes.comprehension import ComprehensionNode
from nodes.generator import GeneratorNode
from nodes.validator import ValidatorNode
from nodes.refiner import RefinerNode


def _con_timing(nombre: str, func):
    """
    Envuelve la función run() de un nodo para medir e imprimir cuánto tarda.
    No modifica el nodo en sí — solo instrumenta desde afuera.
    """
    def wrapper(state):
        t0 = time.perf_counter()
        resultado = func(state)
        elapsed = time.perf_counter() - t0
        print(f"⏱️  {nombre}: {elapsed:.1f}s")
        return resultado
    return wrapper


class CommitGraph:
    """
    Grafo principal del agente.

    Flujo:
    [analyzer] → [comprehension] → [generator] → [validator] → END
                                        ↑               |
                                        └── [refiner] ──┘
    """

    def __init__(self, llm):
        self.analyzer      = AnalyzerNode()
        self.comprehension  = ComprehensionNode(llm)
        self.generator      = GeneratorNode(llm)
        self.validator      = ValidatorNode(llm)
        self.refiner        = RefinerNode(llm)
        self.router         = Router()

    def build(self):
        workflow = StateGraph(AgentState)

        # ── Registro de nodos (instrumentados con timing) ──────────────────
        workflow.add_node("analyzer",      _con_timing("analyzer",      self.analyzer.run))
        workflow.add_node("comprehension", _con_timing("comprehension", self.comprehension.run))
        workflow.add_node("generator",     _con_timing("generator",     self.generator.run))
        workflow.add_node("validator",     _con_timing("validator",     self.validator.run))
        workflow.add_node("refiner",       _con_timing("refiner",       self.refiner.run))

        # ── Flujo principal ────────────────────────────────────────────
        workflow.set_entry_point("analyzer")

        workflow.add_conditional_edges("analyzer", self.router.after_analyzer, {
            "continue": "comprehension",
            "abort":    END
        })

        workflow.add_edge("comprehension", "generator")

        workflow.add_conditional_edges("generator", self.router.after_generator, {
            "continue": "validator",
            "abort":    END
        })

        workflow.add_conditional_edges("validator", self.router.after_validator, {
            "approved": END,
            "refine":   "refiner",
            "abort":    END
        })

        workflow.add_edge("refiner", "generator")

        return workflow.compile()