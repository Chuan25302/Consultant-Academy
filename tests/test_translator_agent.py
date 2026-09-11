from src.agents.translator_agent import TranslatorAgent


class _CapturingGemini:
    def __init__(self):
        self.prompt = ""

    def generate(self, prompt, max_tokens=None, agent_tag="unknown"):
        self.prompt = prompt
        return "## 💡 ประเด็นวันนี้\nok"


def test_translator_sees_the_whole_fact_checked_draft():
    # The FactChecker's verified draft is the grounded source for the
    # Case Study numbers. Truncating it (was [:1500]) forced the model to
    # invent figures for everything past the cut.
    tail_marker = "TAIL-FACT-42 kWh"
    verified = ("ข้อเท็จจริงที่ผ่านการตรวจแล้ว " * 200) + tail_marker  # ~6k chars
    g = _CapturingGemini()
    TranslatorAgent(g).simplify(verified, None, "Topic", "TECHNICAL")
    assert tail_marker in g.prompt
