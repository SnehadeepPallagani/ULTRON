import json
import re
import urllib.request


class UltronDirector:

    def __init__(self):

        self.name = "ULTRON Director"

        # ========================================================
        # SEMANTIC DIRECTOR MODEL
        # ========================================================

        self.semantic_model = "llama3.1:8b"

        self.ollama_url = "http://localhost:11434/api/generate"

        # ========================================================
        # ULTRON BRAIN REGISTRY
        # ========================================================

        self.brains = {

            "velocity": {
                "model": "llama3.1:8b",
                "level": 1,
                "specialization": (
                    "fast general questions, conversation, "
                    "summaries, and simple explanations"
                )
            },

            "forge": {
                "model": "qwen3.5:9b",
                "level": 2,
                "specialization": (
                    "coding, debugging, technical questions, "
                    "mathematics, and structured reasoning"
                )
            },

            "apex": {
                "model": "gemma3:12b",
                "level": 3,
                "specialization": (
                    "analysis, multimodal tasks, documents, "
                    "images, and complex explanations"
                )
            },

            "titan": {
                "model": "gpt-oss:20b",
                "level": 4,
                "specialization": (
                    "deep reasoning, planning, complex coding, "
                    "and difficult multi-step problems"
                )
            }
        }

    # ============================================================
    # RULE-BASED ANALYSIS
    # ============================================================

    def rule_analyze(self, user_input):

        text = user_input.strip()
        lower = text.lower()

        return {
            "intent": self.detect_intent(lower),
            "domain": self.detect_domain(lower),
            "current_information": self.needs_current_information(lower),
            "web_required": self.needs_current_information(lower),
            "images_required": self.needs_images(lower),
            "complexity": self.detect_complexity(lower)
        }

    # ============================================================
    # INTENT DETECTION
    # ============================================================

    def detect_intent(self, text):

        if any(word in text for word in [
            "write code",
            "write a program",
            "python program",
            "java program",
            "c program",
            "c++ program",
            "code for",
            "implement",
            "debug",
            "fix this code",
            "correct this code"
        ]):
            return "coding"

        if any(word in text for word in [
            "latest",
            "current",
            "recent",
            "today",
            "now",
            "news",
            "currently",
            "this week",
            "this month",
            "this year"
        ]):
            return "research"

        if any(word in text for word in [
            "compare",
            "comparison",
            "difference between",
            "differences between",
            "better than",
            "advantages and disadvantages",
            "pros and cons"
        ]):
            return "comparison"

        if any(word in text for word in [
            "explain",
            "what is",
            "how does",
            "why does",
            "meaning of"
        ]):
            return "explanation"

        if any(word in text for word in [
            "research",
            "analyze",
            "analysis",
            "study",
            "investigate"
        ]):
            return "research"

        if any(word in text for word in [
            "plan",
            "planning",
            "architecture",
            "design"
        ]):
            return "planning"

        if any(word in text for word in [
            "creative",
            "story",
            "poem",
            "poster"
        ]):
            return "creative"

        if any(word in text for word in [
            "problem",
            "error",
            "issue",
            "not working",
            "troubleshoot"
        ]):
            return "troubleshooting"

        return "general"

    # ============================================================
    # DOMAIN DETECTION
    # ============================================================

    def detect_domain(self, text):

        domains = {

            "programming": [
                "python",
                "java",
                "c++",
                "c language",
                "javascript",
                "programming",
                "code",
                "algorithm",
                "debug",
                "spring boot",
                "react",
                "sql"
            ],

            "artificial_intelligence": [
                "ai",
                "artificial intelligence",
                "machine learning",
                "deep learning",
                "llm",
                "language model",
                "neural network",
                "tinyml",
                "ai agent",
                "agents"
            ],

            "science": [
                "physics",
                "chemistry",
                "biology",
                "scientific",
                "science"
            ],

            "medical": [
                "medicine",
                "medical",
                "disease",
                "symptoms",
                "treatment",
                "drug",
                "health",
                "diagnosis"
            ],

            "electronics": [
                "arduino",
                "esp32",
                "sensor",
                "circuit",
                "voltage",
                "current",
                "microcontroller",
                "electronics",
                "raspberry pi",
                "embedded"
            ],

            "computer_science": [
                "operating system",
                "database",
                "computer",
                "network",
                "cpu",
                "memory",
                "software",
                "hardware",
                "compiler",
                "data structure"
            ],

            "cloud": [
                "aws",
                "azure",
                "cloud",
                "ec2",
                "s3",
                "lambda",
                "docker",
                "kubernetes"
            ]
        }

        for domain, keywords in domains.items():

            if any(keyword in text for keyword in keywords):
                return domain

        return "general"

    # ============================================================
    # CURRENT INFORMATION
    # ============================================================

    def needs_current_information(self, text):

        current_keywords = [
            "latest",
            "current",
            "recent",
            "today",
            "now",
            "news",
            "currently",
            "this week",
            "this month",
            "this year",
            "new release",
            "new version",
            "latest version",
            "what happened",
            "as of now"
        ]

        return any(
            keyword in text
            for keyword in current_keywords
        )

    # ============================================================
    # IMAGE REQUIREMENT
    # ============================================================

    def needs_images(self, text):

        image_keywords = [
            "image",
            "images",
            "picture",
            "pictures",
            "photo",
            "photos",
            "diagram",
            "visual",
            "show me",
            "look at",
            "see this"
        ]

        return any(
            keyword in text
            for keyword in image_keywords
        )

    # ============================================================
    # COMPLEXITY
    # ============================================================

    def detect_complexity(self, text):

        high_keywords = [
            "deep research",
            "comprehensive",
            "architecture",
            "complex",
            "multi-step",
            "investigate"
        ]

        medium_keywords = [
            "compare",
            "comparison",
            "explain",
            "how",
            "why",
            "design",
            "analyze",
            "analysis"
        ]

        if any(
            keyword in text
            for keyword in high_keywords
        ):
            return "high"

        if any(
            keyword in text
            for keyword in medium_keywords
        ):
            return "medium"

        if len(text.split()) > 15:
            return "medium"

        return "low"

    # ============================================================
    # SEMANTIC DIRECTOR
    # ============================================================

    def semantic_analyze(self, user_input):

        prompt = f"""
You are the semantic planning component of ULTRON.

Do NOT answer the user.

Understand what the user wants and create an execution plan.

USER REQUEST:
{user_input}

Return ONLY valid JSON.

Use exactly this structure:

{{
    "intent": "",
    "domain": "",
    "current_information": false,
    "web_required": false,
    "images_required": false,
    "research_depth": "",
    "complexity": "",
    "recommended_brain": "",
    "output_format": "",
    "tools_required": []
}}

Possible intent values:

general
explanation
coding
research
comparison
creative
analysis
planning
troubleshooting

Possible complexity:

low
medium
high

Possible research_depth:

none
basic
deep

Available brains:

velocity = fast general questions, conversation, summaries

forge = coding, debugging, technical questions, mathematics

apex = analysis, documents, images, multimodal tasks

titan = difficult reasoning, planning, complex multi-step problems

Possible output_format:

paragraph
points
steps
table
code
mixed

Possible tools:

web_search
image_search
vision
code_execution
file_analysis
computer_control

Important rules:

- Understand the actual meaning of the request.
- Do not assume current information is needed for ordinary factual questions.
- Use web_search when current information is genuinely required.
- Use image_search when images are explicitly requested or clearly useful.
- Use vision only when an image must actually be interpreted.
- Use code_execution only when code must actually be executed or verified.
- Use file_analysis only when files or documents are involved.
- Use computer_control only when computer interaction is actually required.
- Coding tasks normally use Forge.
- Technical electronics tasks normally use Forge.
- Images and multimodal tasks normally use Apex.
- Deep research can use Apex or Titan.
- Complex planning can use Titan.
- Simple questions normally use Velocity.
- Do not answer the user.
- Return JSON only.
"""

        payload = {
            "model": self.semantic_model,
            "prompt": prompt,
            "stream": False
        }

        try:

            data = json.dumps(payload).encode("utf-8")

            request = urllib.request.Request(
                self.ollama_url,
                data=data,
                headers={
                    "Content-Type": "application/json"
                },
                method="POST"
            )

            with urllib.request.urlopen(
                request,
                timeout=120
            ) as response:

                result = json.loads(
                    response.read().decode("utf-8")
                )

            raw_response = result.get(
                "response",
                ""
            ).strip()

            return self.extract_json(raw_response)

        except Exception as e:

            return {
                "error": str(e)
            }

    # ============================================================
    # JSON EXTRACTION
    # ============================================================

    def extract_json(self, text):

        try:
            return json.loads(text)

        except json.JSONDecodeError:
            pass

        match = re.search(
            r"\{.*\}",
            text,
            re.DOTALL
        )

        if match:

            try:
                return json.loads(
                    match.group(0)
                )

            except json.JSONDecodeError:
                pass

        return {
            "error": "Semantic Director returned invalid JSON",
            "raw_response": text
        }

    # ============================================================
    # BRAIN VALIDATION
    # ============================================================

    def validate_brain(self, brain):

        if brain in self.brains:
            return brain

        return "velocity"

    # ============================================================
    # DIRECTOR CORRECTION LAYER
    # ============================================================

    def correct_plan(self, plan, rule_plan, user_input):

        text = user_input.lower()

        # --------------------------------------------------------
        # Current-information correction
        # --------------------------------------------------------

        # Deterministic rule layer has stronger authority for
        # obvious current-information keywords.

        if rule_plan["current_information"]:

            plan["current_information"] = True
            plan["web_required"] = True

        # If there is no current-information signal and the
        # question is a normal explanation/general question,
        # prevent unnecessary web usage.

        elif plan.get("intent") in [
            "explanation",
            "general"
        ]:

            plan["current_information"] = False
            plan["web_required"] = False
            plan["research_depth"] = "none"

        # --------------------------------------------------------
        # Image correction
        # --------------------------------------------------------

        if rule_plan["images_required"]:

            plan["images_required"] = True
            plan["web_required"] = True

        # --------------------------------------------------------
        # Technical domain correction
        # --------------------------------------------------------

        technical_domains = [
            "programming",
            "electronics",
            "computer_science",
            "cloud"
        ]

        if (
            plan.get("intent") in [
                "comparison",
                "analysis",
                "troubleshooting"
            ]
            and plan.get("domain") in technical_domains
        ):

            # Don't unnecessarily force Titan.
            if plan.get("recommended_brain") == "titan":
                plan["recommended_brain"] = "forge"

        # --------------------------------------------------------
        # Coding correction
        # --------------------------------------------------------

        if plan.get("intent") == "coding":

            plan["recommended_brain"] = "forge"
            plan["output_format"] = "code"

        # --------------------------------------------------------
        # Image correction
        # --------------------------------------------------------

        if plan.get("images_required"):

            plan["recommended_brain"] = "apex"

        # --------------------------------------------------------
        # Simple explanation correction
        # --------------------------------------------------------

        if (
            plan.get("intent") == "explanation"
            and not plan.get("current_information")
            and not plan.get("images_required")
        ):

            plan["recommended_brain"] = "velocity"

            if plan.get("complexity") not in [
                "medium",
                "high"
            ]:
                plan["complexity"] = "low"

        # --------------------------------------------------------
        # Remove obviously unnecessary tools
        # --------------------------------------------------------

        tools = plan.get(
            "tools_required",
            []
        )

        if not isinstance(tools, list):
            tools = []

        cleaned_tools = []

        for tool in tools:

            if tool not in [
                "web_search",
                "image_search",
                "vision",
                "code_execution",
                "file_analysis",
                "computer_control"
            ]:
                continue

            if tool not in cleaned_tools:
                cleaned_tools.append(tool)

        tools = cleaned_tools

        # Web
        if plan.get("web_required"):

            if "web_search" not in tools:
                tools.append("web_search")

        else:

            tools = [
                tool
                for tool in tools
                if tool != "web_search"
            ]

        # Images
        if plan.get("images_required"):

            if "image_search" not in tools:
                tools.append("image_search")

            if "vision" not in tools:
                tools.append("vision")

        else:

            tools = [
                tool
                for tool in tools
                if tool not in [
                    "image_search",
                    "vision"
                ]
            ]

        # Code execution only for explicit verification needs.
        explicit_execution = any(
            phrase in text
            for phrase in [
                "run the code",
                "execute the code",
                "test the code",
                "verify the code",
                "execute this",
                "run this"
            ]
        )

        if not explicit_execution:

            tools = [
                tool
                for tool in tools
                if tool != "code_execution"
            ]

        # File analysis only when files are mentioned.
        file_terms = [
            "file",
            "document",
            "pdf",
            "excel",
            "spreadsheet",
            "uploaded",
            "attachment"
        ]

        if not any(
            term in text
            for term in file_terms
        ):

            tools = [
                tool
                for tool in tools
                if tool != "file_analysis"
            ]

        plan["tools_required"] = tools

        return plan

    # ============================================================
    # CAPABILITY FLOOR
    # ============================================================

    def determine_required_level(self, plan):

        intent = plan.get(
            "intent",
            "general"
        )

        domain = plan.get(
            "domain",
            "general"
        )

        complexity = plan.get(
            "complexity",
            "low"
        )

        images_required = plan.get(
            "images_required",
            False
        )

        research_depth = plan.get(
            "research_depth",
            "none"
        )

        if images_required:
            return 3

        if intent == "coding":
            return 2

        if domain in [
            "programming",
            "electronics",
            "computer_science",
            "cloud"
        ]:
            return 2

        if research_depth == "deep":
            return 3

        if complexity == "high":
            return 3

        if intent == "planning" and complexity in [
            "medium",
            "high"
        ]:
            return 3

        if domain == "medical" and complexity in [
            "medium",
            "high"
        ]:
            return 3

        return 1

    # ============================================================
    # APPLY CAPABILITY FLOOR
    # ============================================================

    def apply_capability_floor(
        self,
        requested_brain,
        plan
    ):

        requested_brain = self.validate_brain(
            requested_brain
        )

        required_level = self.determine_required_level(
            plan
        )

        requested_level = self.brains[
            requested_brain
        ]["level"]

        final_level = max(
            requested_level,
            required_level
        )

        candidates = sorted(
            self.brains.items(),
            key=lambda item: item[1]["level"]
        )

        for brain_name, brain_data in candidates:

            if brain_data["level"] >= final_level:
                return brain_name

        return "titan"

    # ============================================================
    # BRAIN ROUTER
    # ============================================================

    def route_brain(self, plan):

        requested_brain = plan.get(
            "recommended_brain",
            ""
        ).lower().strip()

        requested_brain = self.validate_brain(
            requested_brain
        )

        final_brain = self.apply_capability_floor(
            requested_brain,
            plan
        )

        return {
            "brain": final_brain,
            "model": self.brains[final_brain]["model"],
            "level": self.brains[final_brain]["level"],
            "specialization": self.brains[
                final_brain
            ]["specialization"]
        }

    # ============================================================
    # PLAN NORMALIZATION
    # ============================================================

    def normalize_plan(
        self,
        rule_plan,
        semantic_plan,
        user_input
    ):

        final_plan = semantic_plan.copy()

        # --------------------------------------------------------
        # Boolean validation
        # --------------------------------------------------------

        if not isinstance(
            final_plan.get("current_information"),
            bool
        ):
            final_plan["current_information"] = (
                rule_plan["current_information"]
            )

        if not isinstance(
            final_plan.get("web_required"),
            bool
        ):
            final_plan["web_required"] = (
                rule_plan["web_required"]
            )

        if not isinstance(
            final_plan.get("images_required"),
            bool
        ):
            final_plan["images_required"] = (
                rule_plan["images_required"]
            )

        # --------------------------------------------------------
        # Missing values
        # --------------------------------------------------------

        if not final_plan.get("intent"):
            final_plan["intent"] = rule_plan["intent"]

        if not final_plan.get("domain"):
            final_plan["domain"] = rule_plan["domain"]

        if not final_plan.get("complexity"):
            final_plan["complexity"] = rule_plan["complexity"]

        # --------------------------------------------------------
        # Research depth
        # --------------------------------------------------------

        if final_plan.get("research_depth") not in [
            "none",
            "basic",
            "deep"
        ]:

            if final_plan["web_required"]:
                final_plan["research_depth"] = "basic"
            else:
                final_plan["research_depth"] = "none"

        # --------------------------------------------------------
        # Output format
        # --------------------------------------------------------

        valid_formats = [
            "paragraph",
            "points",
            "steps",
            "table",
            "code",
            "mixed"
        ]

        if final_plan.get("output_format") not in valid_formats:

            final_plan["output_format"] = "paragraph"

        # --------------------------------------------------------
        # Tools
        # --------------------------------------------------------

        if not isinstance(
            final_plan.get("tools_required"),
            list
        ):
            final_plan["tools_required"] = []

        # --------------------------------------------------------
        # Correction layer
        # --------------------------------------------------------

        final_plan = self.correct_plan(
            final_plan,
            rule_plan,
            user_input
        )

        # --------------------------------------------------------
        # Capability floor
        # --------------------------------------------------------

        final_plan["required_capability_level"] = (
            self.determine_required_level(
                final_plan
            )
        )

        final_plan["brain_route"] = self.route_brain(
            final_plan
        )

        final_plan["recommended_brain"] = (
            final_plan["brain_route"]["brain"]
        )

        return final_plan

    # ============================================================
    # MAIN ANALYSIS
    # ============================================================

    def analyze(self, user_input):

        rule_plan = self.rule_analyze(
            user_input
        )

        semantic_plan = self.semantic_analyze(
            user_input
        )

        # --------------------------------------------------------
        # Semantic failure
        # --------------------------------------------------------

        if "error" in semantic_plan:

            fallback_plan = rule_plan.copy()

            fallback_plan["recommended_brain"] = (
                self.fallback_brain(
                    rule_plan
                )
            )

            fallback_plan["research_depth"] = (
                "basic"
                if rule_plan["web_required"]
                else "none"
            )

            fallback_plan["output_format"] = (
                self.fallback_output_format(
                    rule_plan
                )
            )

            fallback_plan["tools_required"] = []

            if rule_plan["web_required"]:
                fallback_plan["tools_required"].append(
                    "web_search"
                )

            if rule_plan["images_required"]:
                fallback_plan["tools_required"].append(
                    "image_search"
                )

            fallback_plan = self.correct_plan(
                fallback_plan,
                rule_plan,
                user_input
            )

            fallback_plan["required_capability_level"] = (
                self.determine_required_level(
                    fallback_plan
                )
            )

            fallback_plan["brain_route"] = (
                self.route_brain(
                    fallback_plan
                )
            )

            fallback_plan["recommended_brain"] = (
                fallback_plan["brain_route"]["brain"]
            )

            return {
                "director": self.name,
                "mode": "rule_fallback",
                "final_plan": fallback_plan
            }

        # --------------------------------------------------------
        # Semantic success
        # --------------------------------------------------------

        final_plan = self.normalize_plan(
            rule_plan,
            semantic_plan,
            user_input
        )

        return {
            "director": self.name,
            "mode": "semantic",
            "final_plan": final_plan
        }

    # ============================================================
    # FALLBACK BRAIN SELECTION
    # ============================================================

    def fallback_brain(self, rule_plan):

        if rule_plan["images_required"]:
            return "apex"

        if rule_plan["intent"] == "coding":
            return "forge"

        if rule_plan["intent"] == "comparison":

            if rule_plan["domain"] in [
                "programming",
                "electronics",
                "computer_science",
                "cloud"
            ]:
                return "forge"

            return "apex"

        if rule_plan["intent"] == "research":
            return "apex"

        if rule_plan["complexity"] == "high":
            return "titan"

        if rule_plan["domain"] in [
            "programming",
            "electronics",
            "computer_science",
            "cloud"
        ]:
            return "forge"

        return "velocity"

    # ============================================================
    # FALLBACK OUTPUT FORMAT
    # ============================================================

    def fallback_output_format(self, rule_plan):

        if rule_plan["intent"] == "coding":
            return "code"

        if rule_plan["intent"] in [
            "research",
            "comparison"
        ]:
            return "points"

        if rule_plan["intent"] == "planning":
            return "steps"

        return "paragraph"


# ================================================================
# TEST MODE
# ================================================================

if __name__ == "__main__":

    director = UltronDirector()

    print("ULTRON DIRECTOR ONLINE")
    print("----------------------------------------")
    print(
        "Semantic model:",
        director.semantic_model
    )

    print("\nAvailable brains:")

    for name, brain in director.brains.items():

        print(
            f"- {name}: "
            f"{brain['model']} "
            f"(Level {brain['level']})"
        )

    while True:

        user_input = input("\nYOU: ").strip()

        if user_input.lower() in [
            "exit",
            "quit"
        ]:
            break

        if not user_input:
            continue

        result = director.analyze(
            user_input
        )

        print("\nNORMALIZED DIRECTOR PLAN:")

        print(
            json.dumps(
                result,
                indent=4
            )
        )