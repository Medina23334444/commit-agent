# src/agent/graph.py
from langgraph.graph import StateGraph, END
from agent.state import AgentState
from agent.router import Router
from nodes.analyzer import AnalyzerNode
from nodes.comprehension import ComprehensionNode
from nodes.generator import GeneratorNode
from nodes.validator import ValidatorNode
from nodes.refiner import RefinerNode


class CommitGraph:
    """
    Grafo principal del agente.
    
    Flujo:
    [analyzer] → [comprehension] → [generator] → [validator] → END
                                        ↑               |
                                        └── [refiner] ──┘
    """

    def __init__(self, llm):
        # ── Nodos ─────────────────────────────────────────────────────
        self.analyzer     = AnalyzerNode()
        self.comprehension = ComprehensionNode(llm)
        self.generator    = GeneratorNode(llm)
        self.validator    = ValidatorNode(llm)
        self.refiner      = RefinerNode(llm)
        self.router       = Router()

    def build(self):
        workflow = StateGraph(AgentState)

        # ── Registro de nodos ──────────────────────────────────────────
        workflow.add_node("analyzer",     self.analyzer.run)
        workflow.add_node("comprehension", self.comprehension.run)
        workflow.add_node("generator",    self.generator.run)
        workflow.add_node("validator",    self.validator.run)
        workflow.add_node("refiner",      self.refiner.run)

        # ── Flujo principal ────────────────────────────────────────────
        workflow.set_entry_point("analyzer")

        # Pilar 1 — salida temprana si no hay diff o error de git
        workflow.add_conditional_edges("analyzer", self.router.after_analyzer, {
            "continue": "comprehension",
            "abort":    END
        })

        # Comprehension → Generator
        workflow.add_edge("comprehension", "generator")

        # Pilar 2 — salida temprana si la API falla
        workflow.add_conditional_edges("generator", self.router.after_generator, {
            "continue": "validator",
            "abort":    END
        })

        # Pilar 3 — bucle de refinamiento semántico
        workflow.add_conditional_edges("validator", self.router.after_validator, {
            "approved": END,
            "refine":   "refiner",
            "abort":    END
        })

        # Refiner vuelve al generator con la crítica como contexto
        workflow.add_edge("refiner", "generator")

        return workflow.compile()