from typing import Any, List, Dict, Tuple

class ParseError(Exception):
    pass

class Token:
    def __init__(self, type_: str, value: str):
        self.type = type_
        self.value = value

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)})"

def tokenize(text: str) -> List[Token]:
    tokens = []
    i = 0
    while i < len(text):
        char = text[i]
        if char.isspace():
            i += 1
            continue

        if char in "=[],()":
            tokens.append(Token("PUNCT", char))
            i += 1
            continue

        if char in ("'", '"'):
            quote = char
            i += 1
            start = i
            while i < len(text) and text[i] != quote:
                if text[i] == '\\':
                    i += 2 # skip escaped char
                else:
                    i += 1
            if i >= len(text):
                raise ParseError("Unterminated string")
            val = text[start:i]
            # Unescape basic backslashes (like \' or \")
            val = val.replace("\\" + quote, quote).replace("\\\\", "\\")
            tokens.append(Token("STRING", val))
            i += 1
            continue

        if char.isalpha() or char == '_':
            start = i
            while i < len(text) and (text[i].isalnum() or text[i] == '_'):
                i += 1
            val = text[start:i]
            if val in ("None", "True", "False"):
                tokens.append(Token("KEYWORD", val))
            else:
                tokens.append(Token("IDENTIFIER", val))
            continue

        if char.isdigit() or char == '-':
            start = i
            while i < len(text) and (text[i].isdigit() or text[i] == '.' or text[i] == '-'):
                i += 1
            val = text[start:i]
            tokens.append(Token("NUMBER", val))
            continue

        raise ParseError(f"Unexpected character: {char} at index {i}")

    return tokens

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token | None:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected_type: str = None, expected_value: str = None) -> Token:
        t = self.peek()
        if not t:
            raise ParseError("Unexpected end of input")
        if expected_type and t.type != expected_type:
            raise ParseError(f"Expected type {expected_type}, got {t.type} (value: {t.value})")
        if expected_value and t.value != expected_value:
            raise ParseError(f"Expected value {expected_value}, got {t.value}")
        self.pos += 1
        return t

    def parse_value(self) -> Any:
        t = self.peek()
        if not t:
            raise ParseError("Unexpected end of input while parsing value")

        if t.type == "KEYWORD":
            self.consume()
            if t.value == "None": return None
            if t.value == "True": return True
            if t.value == "False": return False

        if t.type == "STRING":
            self.consume()
            return t.value

        if t.type == "NUMBER":
            self.consume()
            return float(t.value) if '.' in t.value else int(t.value)

        if t.type == "PUNCT" and t.value == "[":
            return self.parse_list()

        if t.type == "IDENTIFIER":
            ident = self.consume().value
            next_t = self.peek()
            if next_t and next_t.type == "PUNCT" and next_t.value == "(":
                return self.parse_class(ident)
            else:
                # Some unquoted enums or fallback strings
                return ident

        raise ParseError(f"Unexpected token while parsing value: {t}")

    def parse_list(self) -> List[Any]:
        self.consume("PUNCT", "[")
        result = []
        while self.peek() and not (self.peek().type == "PUNCT" and self.peek().value == "]"):
            result.append(self.parse_value())
            nxt = self.peek()
            if nxt and nxt.type == "PUNCT" and nxt.value == ",":
                self.consume()
        self.consume("PUNCT", "]")
        return result

    def parse_class(self, class_name: str) -> Dict[str, Any]:
        self.consume("PUNCT", "(")
        result = {"__class__": class_name}
        while self.peek() and not (self.peek().type == "PUNCT" and self.peek().value == ")"):
            key = self.consume("IDENTIFIER").value
            self.consume("PUNCT", "=")
            val = self.parse_value()
            result[key] = val
            nxt = self.peek()
            if nxt and nxt.type == "PUNCT" and nxt.value == ",":
                self.consume()
        self.consume("PUNCT", ")")
        return result

    def parse_top_level(self) -> Dict[str, Any]:
        """
        Parses space-separated key=value pairs into a dict.
        e.g. status='NO_APPROVAL_REQUIRED' original_quote_risk_result=QuoteRiskResult(...) ...
        """
        result = {}
        while self.peek():
            key = self.consume("IDENTIFIER").value
            self.consume("PUNCT", "=")
            val = self.parse_value()
            result[key] = val
        return result

def parse_agent_response(text: str) -> Dict[str, Any]:
    """
    Deterministically parses the Python repr string returned by the hosted agent
    into a structured JSON-serializable dictionary.
    """
    tokens = tokenize(text)
    parser = Parser(tokens)
    return parser.parse_top_level()
