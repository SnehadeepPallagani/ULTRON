import json
import urllib.request
import urllib.error

from director import UltronDirector
from research import conduct_research
from context_engine import ContextEngine


class UltronExecutor:

    def __init__(self):

        self.director = UltronDirector()
        self.context_engine = ContextEngine()

        self.ollama_url = (
            "http://localhost:11434/api/generate"
        )

    # =========================================================
    # CALL BRAIN
    # =========================================================

    def call_brain(
        self,
        model,
        user_input,
        plan,
        research_context=None
    ):

        context_contract = plan.get(
            "context_contract",
            {}
        )

        system_instruction = """
You are ULTRON, a personal AI system created,
designed, developed, and architected by
Snehadeep Pallagani.

Your job is to understand the user's actual request
and respond appropriately.

IMPORTANT BEHAVIOR:

1. Do not invent meanings for unfamiliar terminology.
2. Do not turn capability questions into execution tasks.
3. Do not turn explanation questions into execution tasks.
4. Do not invent requirements, frameworks, libraries,
   technologies, or design choices that the user did not request.
5. If the user asks whether you can perform something,
   answer whether you can perform it and briefly explain how.
6. If the user asks what something means, explain it.
7. If the user asks to build something, treat it as a
   construction task.
8. If the user asks to modify something existing, preserve
   its existing functionality and modify it rather than
   creating an unrelated replacement.
9. If something is genuinely ambiguous, ask a concise
   clarification instead of guessing.
10. Do not claim something works unless it has actually
    been tested or verified.
11. Do not repeatedly call the user "Sir".
12. Do not mention your internal brain routing unless asked.
13. Give useful, complete answers without unnecessary filler.
14. Use Markdown when it improves readability.
"""

        if context_contract:

            system_instruction += f"""

CURRENT ULTRON CONTEXT CONTRACT:

{json.dumps(context_contract, indent=2)}

This contract represents ULTRON's current understanding
of the user's request.

Follow it unless the user's actual wording clearly
contradicts it.
"""

        if research_context:

            system_instruction += f"""

WEB RESEARCH EVIDENCE:

{research_context}

Use this evidence when answering current or research-based
questions.

Do not invent sources or claim unsupported web findings.
"""

        prompt = f"""
{system_instruction}

EXECUTION PLAN:

{json.dumps(plan, indent=2)}

USER REQUEST:

{user_input}

Now provide the best direct answer.
"""

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False
        }

        data = json.dumps(
            payload
        ).encode("utf-8")

        request = urllib.request.Request(
            self.ollama_url,
            data=data,
            headers={
                "Content-Type": "application/json"
            },
            method="POST"
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=120
            ) as response:

                result = json.loads(
                    response.read().decode(
                        "utf-8"
                    )
                )

            return result.get(
                "response",
                ""
            ).strip()

        except urllib.error.URLError as error:

            raise RuntimeError(
                f"Ollama connection failed: {error}"
            )

        except TimeoutError:

            raise RuntimeError(
                "The selected ULTRON brain timed out."
            )

    # =========================================================
    # BUILD DETERMINISTIC PLAN
    # =========================================================

    def build_context_plan(
        self,
        user_input,
        context_contract
    ):

        intent = context_contract.get(
            "intent",
            "general"
        )

        domain = context_contract.get(
            "domain",
            "general"
        )

        task_type = context_contract.get(
            "task_type",
            "question_answering"
        )

        action = context_contract.get(
            "action",
            "answer"
        )

        artifact = context_contract.get(
            "artifact"
        )

        # -----------------------------------------------------
        # Start with Director's deterministic analysis
        # -----------------------------------------------------

        plan = self.director.rule_analyze(
            user_input
        )

        # -----------------------------------------------------
        # Context Engine is authoritative for clear requests.
        # -----------------------------------------------------

        plan["intent"] = intent

        # Map Context domain into Director domain where possible.

        domain_mapping = {

            "software": "programming",

            "ai": "artificial_intelligence",

            "hardware": "electronics",

            "academic": "computer_science",

            "science": "science",

            "business": "general",

            "general": "general"
        }

        plan["domain"] = domain_mapping.get(
            domain,
            "general"
        )

        # -----------------------------------------------------
        # Capability questions
        # -----------------------------------------------------

        if intent == "capability_question":

            plan["intent"] = (
                "capability_question"
            )

            plan["current_information"] = False
            plan["web_required"] = False
            plan["images_required"] = False
            plan["research_depth"] = "none"
            plan["complexity"] = "low"
            plan["recommended_brain"] = "velocity"
            plan["output_format"] = "paragraph"
            plan["tools_required"] = []

        # -----------------------------------------------------
        # Explanations
        # -----------------------------------------------------

        elif intent == "explanation":

            plan["intent"] = "explanation"

            plan["current_information"] = False
            plan["web_required"] = False
            plan["images_required"] = False
            plan["research_depth"] = "none"
            plan["recommended_brain"] = "velocity"
            plan["output_format"] = "mixed"
            plan["tools_required"] = []

        # -----------------------------------------------------
        # Software creation
        # -----------------------------------------------------

        elif task_type == "software_creation":

            plan["intent"] = "coding"
            plan["domain"] = "programming"
            plan["recommended_brain"] = "forge"
            plan["output_format"] = "code"

        # -----------------------------------------------------
        # Software modification
        # -----------------------------------------------------

        elif task_type in {
            "software_modification",
            "artifact_modification"
        }:

            plan["intent"] = "coding"
            plan["domain"] = "programming"
            plan["recommended_brain"] = "forge"
            plan["output_format"] = "mixed"

        # -----------------------------------------------------
        # Research
        # -----------------------------------------------------

        elif intent == "research":

            plan["intent"] = "research"

        # -----------------------------------------------------
        # Store Context information
        # -----------------------------------------------------

        plan["context_contract"] = (
            context_contract
        )

        plan["context_task_type"] = (
            task_type
        )

        plan["context_action"] = (
            action
        )

        plan["context_artifact"] = (
            artifact
        )

        return plan

    # =========================================================
    # BUILD EXECUTION PLAN
    # =========================================================

    def build_execution_plan(
        self,
        user_input,
        context_contract,
        director_plan
    ):

        brain_route = director_plan[
            "brain_route"
        ]

        execution_plan = {

            "user_input":
                user_input,

            "context_contract":
                context_contract,

            "context_intent":
                context_contract.get(
                    "intent"
                ),

            "context_task_type":
                context_contract.get(
                    "task_type"
                ),

            "context_domain":
                context_contract.get(
                    "domain"
                ),

            "context_action":
                context_contract.get(
                    "action"
                ),

            "context_artifact":
                context_contract.get(
                    "artifact"
                ),

            "context_confidence":
                context_contract.get(
                    "confidence"
                ),

            "intent":
                director_plan.get(
                    "intent"
                ),

            "domain":
                director_plan.get(
                    "domain"
                ),

            "current_information":
                director_plan.get(
                    "current_information",
                    False
                ),

            "web_required":
                director_plan.get(
                    "web_required",
                    False
                ),

            "images_required":
                director_plan.get(
                    "images_required",
                    False
                ),

            "research_depth":
                director_plan.get(
                    "research_depth",
                    "none"
                ),

            "complexity":
                director_plan.get(
                    "complexity",
                    "low"
                ),

            "brain":
                brain_route[
                    "brain"
                ],

            "model":
                brain_route[
                    "model"
                ],

            "tools_required":
                director_plan.get(
                    "tools_required",
                    []
                ),

            "output_format":
                director_plan.get(
                    "output_format",
                    "paragraph"
                ),

            "status":
                "EXECUTING"
        }

        return execution_plan

    # =========================================================
    # EXECUTE
    # =========================================================

    def execute(
        self,
        user_input,
        conversation_history=None
    ):

        # =====================================================
        # 1. CONTEXT ENGINE
        # =====================================================

        print()
        print("ULTRON CONTEXT")
        print("-" * 50)

        context_contract = (
            self.context_engine.analyze(
                user_input,
                conversation_history
            )
        )

        print(
            "Understanding:",
            context_contract[
                "understanding"
            ]
        )

        print(
            "Confidence:",
            context_contract[
                "confidence"
            ]
        )

        # -----------------------------------------------------
        # Clarification
        # -----------------------------------------------------

        if context_contract.get(
            "clarification_needed",
            False
        ):

            answer = (
                "I want to make sure I understand correctly. "
                "Could you clarify what you want me to do?"
            )

            return {

                "plan": {

                    "context_contract":
                        context_contract,

                    "status":
                        "CLARIFICATION_REQUIRED"
                },

                "answer":
                    answer,

                "research":
                    None
            }

        # =====================================================
        # 2. DIRECTOR
        # =====================================================

        context_confidence = context_contract.get(
            "confidence",
            0
        )

        context_intent = context_contract.get(
            "intent"
        )

        # -----------------------------------------------------
        # CLEAR REQUEST
        #
        # Do NOT invoke the slow semantic Director.
        # -----------------------------------------------------

        clear_context = (
            context_confidence >= 0.80
            and context_intent in {
                "capability_question",
                "explanation",
                "software_task",
                "modification",
                "research"
            }
        )

        if clear_context:

            print(
                "Director mode: "
                "deterministic context-guided"
            )

            director_plan = (
                self.build_context_plan(
                    user_input,
                    context_contract
                )
            )

        else:

            print(
                "Director mode: "
                "semantic analysis"
            )

            director_result = (
                self.director.analyze(
                    user_input
                )
            )

            director_plan = (
                director_result[
                    "final_plan"
                ]
            )

        # =====================================================
        # 3. NORMALIZE DIRECTOR PLAN
        # =====================================================

        # Capability question
        if context_intent == (
            "capability_question"
        ):

            director_plan["intent"] = (
                "capability_question"
            )

            director_plan["recommended_brain"] = (
                "velocity"
            )

            director_plan["web_required"] = False
            director_plan["current_information"] = False
            director_plan["images_required"] = False
            director_plan["research_depth"] = "none"
            director_plan["tools_required"] = []
            director_plan["output_format"] = "paragraph"

        # Explanation
        elif context_intent == "explanation":

            director_plan["intent"] = (
                "explanation"
            )

            director_plan["recommended_brain"] = (
                "velocity"
            )

            director_plan["web_required"] = False
            director_plan["current_information"] = False
            director_plan["images_required"] = False
            director_plan["research_depth"] = "none"
            director_plan["tools_required"] = []
            director_plan["output_format"] = "mixed"

        # =====================================================
        # 4. BRAIN ROUTING
        # =====================================================

        director_plan[
            "required_capability_level"
        ] = self.director.determine_required_level(
            director_plan
        )

        director_plan[
            "brain_route"
        ] = self.director.route_brain(
            director_plan
        )

        director_plan[
            "recommended_brain"
        ] = director_plan[
            "brain_route"
        ][
            "brain"
        ]

        # =====================================================
        # 5. EXECUTION PLAN
        # =====================================================

        execution_plan = (
            self.build_execution_plan(
                user_input,
                context_contract,
                director_plan
            )
        )

        brain = execution_plan[
            "brain"
        ]

        model = execution_plan[
            "model"
        ]

        web_required = execution_plan[
            "web_required"
        ]

        # =====================================================
        # 6. RESEARCH
        # =====================================================

        research_result = None
        research_context = None

        if web_required:

            print()
            print("ULTRON RESEARCH")
            print("-" * 50)

            research_result = conduct_research(
                user_input
            )

            research_context = (
                research_result.get(
                    "context",
                    ""
                )
            )

            results = (
                research_result.get(
                    "results",
                    []
                )
            )

            queries = (
                research_result.get(
                    "queries",
                    []
                )
            )

            success = (
                research_result.get(
                    "success",
                    False
                )
            )

            print(
                f"Queries: {len(queries)}"
            )

            print(
                f"Sources found: {len(results)}"
            )

            if not success or not results:

                execution_plan[
                    "status"
                ] = "RESEARCH_UNAVAILABLE"

                answer = (
                    "I couldn't obtain reliable web "
                    "sources for this request right now, "
                    "so I won't present an unverified "
                    "current answer."
                )

                print()
                print("ULTRON")
                print("=" * 50)
                print(answer)

                return {

                    "plan":
                        execution_plan,

                    "answer":
                        answer,

                    "research":
                        research_result
                }

        # =====================================================
        # 7. EXECUTION PLAN
        # =====================================================

        print()
        print("ULTRON EXECUTION PLAN")

        print(
            json.dumps(
                execution_plan,
                indent=4
            )
        )

        # =====================================================
        # 8. BRAIN
        # =====================================================

        answer = self.call_brain(
            model,
            user_input,
            execution_plan,
            research_context
        )

        execution_plan[
            "status"
        ] = "COMPLETED"

        print()
        print("ULTRON")
        print("=" * 50)
        print(answer)

        return {

            "plan":
                execution_plan,

            "answer":
                answer,

            "research":
                research_result
        }


# =============================================================
# TERMINAL TEST
# =============================================================

if __name__ == "__main__":

    print(
        "ULTRON EXECUTOR ONLINE"
    )

    print(
        "Context → Director → "
        "Research → Internet → Brain"
    )

    print()

    executor = UltronExecutor()

    conversation_history = []

    while True:

        user_input = input(
            "YOU: "
        ).strip()

        if not user_input:
            continue

        if user_input.lower() in {
            "exit",
            "quit"
        }:

            print(
                "ULTRON EXECUTOR OFFLINE"
            )

            break

        try:

            result = executor.execute(
                user_input,
                conversation_history
            )

            conversation_history.append({

                "role":
                    "user",

                "content":
                    user_input
            })

            conversation_history.append({

                "role":
                    "assistant",

                "content":
                    result.get(
                        "answer",
                        ""
                    )
            })

        except KeyboardInterrupt:

            print(
                "\nULTRON EXECUTOR INTERRUPTED"
            )

            break

        except Exception as error:

            print()
            print(
                "ULTRON ERROR"
            )
            print(
                error
            )