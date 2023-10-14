#!/usr/bin/env python3

#-------------------------------------------------------------------#
# Copyright (C) 2019-2023 by Serguei Tarassov <serge@arbinada.com>  #
# Distributed freely under the MIT License                          #
#-------------------------------------------------------------------#

"""
JSON stream (SAX) parser

Python port of my C++ parsers (https://github.com/arbinada-com/stdext)
"""

import io
import enum

UTF16_MAX_CHAR = 0x10FFFF
UTF16_BOMS     = {0xFFFE, 0xFEFF}

class Token(enum.IntEnum):
    UNKNOWN         = 0,
    BEGIN_ARRAY     = 10,
    BEGIN_OBJECT    = 20,
    END_ARRAY       = 30,
    END_OBJECT      = 40,
    LITERAL_FALSE   = 50,
    LITERAL_NULL    = 60,
    LITERAL_TRUE    = 70,
    NAME_SEPARATOR  = 80,
    NUMBER_DECIMAL  = 90,
    NUMBER_FLOAT    = 100,
    NUMBER_INT      = 110,
    STRING          = 120,
    VALUE_SEPARATOR = 130

    @staticmethod
    def is_literal_token(tok) -> bool:
        return tok in [Token.LITERAL_FALSE, Token.LITERAL_NULL, Token.LITERAL_TRUE]

class LiteralTokenKind(enum.IntEnum):
    LT_UNKNOWN = 0,
    LT_FALSE   = 10,
    LT_NULL    = 20,
    LT_TRUE    = 30

class NumericTokenKind(enum.IntEnum):
    NT_UNKNOWN = 0,
    NT_INTEGER = 10,
    NT_DECIMAL = 20,
    NT_FLOAT   = 30


class TextPos:
    def __init__(self, line: int = 1, col: int = 0) -> None:
        self.line = line
        self.col = col

    def __str__(self) -> str:
        return f"Line: {self.line}, col: {self.col}"

    def __eq__(self, other) -> bool:
        return self.line == other.line and self.col == other.col

    def newline(self):
        self.line += 1
        self.col = 0

    def make_copy(self):
        return TextPos(self.line, self.col)


class JSONParserMessage:
    # Lexer messages
    ERR_INVALID_LITERAL_FMT            = 1010
    ERR_INVALID_NUMBER                 = 1020
    ERR_UNALLOWED_CHAR_FMT             = 1030
    ERR_UNALLOWED_ESCAPE_SEQ           = 1040
    ERR_UNCLOSED_STRING                = 1050
    ERR_UNEXPECTED_CHAR_FMT            = 1060
    ERR_UNRECOGNIZED_ESCAPE_SEQ_FMT    = 1070
    # Parser messages
    ERR_EXPECTED_ARRAY                 = 2100,
    ERR_EXPECTED_ARRAY_ITEM            = 2105,
    ERR_EXPECTED_EOF                   = 2107,
    ERR_EXPECTED_LITERAL               = 2110,
    ERR_EXPECTED_MEMBER_NAME           = 2112,
    ERR_EXPECTED_NAME_SEPARATOR        = 2014,
    ERR_EXPECTED_NUMBER                = 2116,
    ERR_EXPECTED_OBJECT                = 2120,
    ERR_EXPECTED_STRING                = 2125,
    ERR_EXPECTED_VALUE                 = 2150,
    ERR_EXPECTED_VALUE_BUT_FOUND_FMT   = 2155,
    ERR_MEMBER_NAME_DUPLICATE_FMT      = 2200,
    ERR_MEMBER_NAME_IS_EMPTY           = 2205,
    ERR_PARENT_IS_NOT_CONTAINER        = 2250,
    ERR_UNCLOSED_ARRAY                 = 2290,
    ERR_UNCLOSED_OBJECT                = 2295,
    ERR_UNEXPECTED_LEXEME_FMT          = 2300,
    ERR_UNEXPECTED_TEXT_END            = 2310,
    ERR_UNSUPPORTED_DOM_VALUE_TYPE_FMT = 2400


    _MESSAGES = {
        ERR_UNALLOWED_ESCAPE_SEQ          : "Unallowed escape sequention",
        ERR_INVALID_LITERAL_FMT           : "Invalid literal: {}",
        ERR_INVALID_NUMBER                : "Invalid number",
        ERR_UNALLOWED_CHAR_FMT            : "Unallowed char '{}'",
        ERR_UNCLOSED_STRING               : "Unclosed string",
        ERR_UNEXPECTED_CHAR_FMT           : "Unexpected character: {}",
        ERR_UNRECOGNIZED_ESCAPE_SEQ_FMT   : "Unrecognized escape sequence: {}",
        #
        ERR_EXPECTED_ARRAY                : "Array expected",
        ERR_EXPECTED_ARRAY_ITEM           : "Array item expected",
        ERR_EXPECTED_EOF                  : "End of document expected",
        ERR_EXPECTED_LITERAL              : "Literal expected",
        ERR_EXPECTED_MEMBER_NAME          : "Object member name expected",
        ERR_EXPECTED_NAME_SEPARATOR       : "Name separator ':' expected",
        ERR_EXPECTED_NUMBER               : "Number expected",
        ERR_EXPECTED_OBJECT               : "Object expected",
        ERR_EXPECTED_STRING               : "String expected",
        ERR_EXPECTED_VALUE                : "Expected value",
        ERR_EXPECTED_VALUE_BUT_FOUND_FMT  : "Expected value but '%ls' found",
        ERR_MEMBER_NAME_DUPLICATE_FMT     : "Duplicate member name '%ls'",
        ERR_MEMBER_NAME_IS_EMPTY          : "Member name is empty",
        ERR_PARENT_IS_NOT_CONTAINER       : "Parent DOM value is not container",
        ERR_UNCLOSED_ARRAY                : "Unclosed array",
        ERR_UNCLOSED_OBJECT               : "Unclosed object",
        ERR_UNEXPECTED_LEXEME_FMT         : "Unexpected '%ls'",
        ERR_UNEXPECTED_TEXT_END           : "Unexpected end of text",
        ERR_UNSUPPORTED_DOM_VALUE_TYPE_FMT: "Unsupported DOM value type: %ls"
    }

    @staticmethod
    def text(msg_id: int, *args) -> str:
        msg = JSONParserMessage._MESSAGES.get(msg_id, None)
        if msg is None:
            return f"Unknown message ID: {msg_id}"
        return msg.format(args)

class JSONError(Exception):
    """
    Base exception class for the module
    """

class JSONParserError(JSONError):
    def __init__(self, pos: TextPos, msg_id: int, *args) -> None:
        self._pos = pos
        self._msg_id = msg_id
        msg = JSONParserMessage.text(msg_id, args)
        super().__init__(msg)

    def __str__(self) -> str:
        result = ""
        if self._pos is not None:
            result += f"{str(self._pos)}. "
        result += super().__str__()
        return result

    @property
    def msg_id(self) -> int:
        return self._msg_id

    @property
    def pos(self) -> TextPos:
        return self._pos


class Lexeme:
    def __init__(self, pos: TextPos, tok: Token = Token.UNKNOWN, text: str = "", 
                 literal_kind: LiteralTokenKind = LiteralTokenKind.LT_UNKNOWN,
                 numeric_kind: NumericTokenKind = NumericTokenKind.NT_UNKNOWN) -> None:
        self._pos = pos
        self._token = tok
        self._text = text
        self._literal_kind = literal_kind
        self._numeric_kind = numeric_kind

    @property
    def pos(self) -> TextPos:
        return self._pos

    @property
    def text(self) -> str:
        return self._text

    @property
    def token(self) -> Token:
        return self._token

    @property
    def literal_kind(self) -> LiteralTokenKind:
        return self._literal_kind
    
    @property
    def numeric_kind(self) -> NumericTokenKind:
        return self._numeric_kind


class NumericParser:
    EXP_CHARS = {'e', 'E'}

    def __init__(self) -> None:
        self._char_count = 0
        self._digit_count = 0
        self._type = NumericTokenKind.NT_UNKNOWN
        self._accepting_type = NumericTokenKind.NT_INTEGER
        self._value = ""

    def accept(self, c: str):
        self._char_count += 1
        self._value += c

    def read_string(self, s: str) -> bool:
        for c in s:
            if not self.read_char(c):
                self._type = NumericTokenKind.NT_UNKNOWN
                break
        return self.is_valid_number()

    def read_char(self, c: str) -> bool:
        if c == '-':
            if self._char_count == 0:
                self.accept(c)
        elif c == '+':
            if self._accepting_type == NumericTokenKind.NT_FLOAT and self._char_count == 0:
                self.accept(c)
            else:
                return False
        elif c == '.':
            if self._accepting_type == NumericTokenKind.NT_INTEGER and self._digit_count > 0:
                self.accept(c)
                self._accepting_type = NumericTokenKind.NT_DECIMAL
                self._type = NumericTokenKind.NT_UNKNOWN
            else:
                return False
        elif c.isdigit():
            if self._accepting_type == NumericTokenKind.NT_INTEGER and self._digit_count == 1 and self._value == "0":
                self._type = NumericTokenKind.NT_UNKNOWN
                return False
            self.accept(c)
            self._digit_count += 1
            self._type = self._accepting_type
        elif c in NumericParser.EXP_CHARS:
            if self._accepting_type == NumericTokenKind.NT_INTEGER or self._accepting_type == NumericTokenKind.NT_DECIMAL:
                self.accept(c)
                self._char_count = 0
                self._digit_count = 0
                self._type = NumericTokenKind.NT_UNKNOWN
                self._accepting_type = NumericTokenKind.NT_FLOAT
            else:
                self._type = NumericTokenKind.NT_UNKNOWN
                return False
        else:
            return False
        return True

    @property
    def type(self) -> NumericTokenKind:
        return self._type
    
    @property
    def value(self) -> str:
        return self._value


class Lexer:

    DEC_DIGITS       = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9'}
    DEC_DIGITS_S     = DEC_DIGITS.union({'-', "+"})
    HEX_DIGITS       = {'a', 'A', 'b', 'B', 'c', 'C', 'd', 'D', 'e', 'E', 'f', 'F'}
    WHITESPACES      = {' ', '\t', '\r', '\n'}
    LITERAL_PREFIXES = {'f', 'n', 't'}
    STRUCTURALS = {
        '[': Token.BEGIN_ARRAY,
        '{': Token.BEGIN_OBJECT,
        ']': Token.END_ARRAY,
        '}': Token.END_OBJECT,
        ':': Token.NAME_SEPARATOR,
        ',': Token.VALUE_SEPARATOR 
    }
    ESCAPE_CHARS = {
        '"': '"',
        '\\': '\\',
        '/': '/',
        'b': '\b',
        'f': '\f',
        'n': '\n',
        'r': '\r',
        't': '\t'
    }

    def __init__(self, reader: io.TextIOBase) -> None:
        self._reader = reader
        self._eof = False
        self._initial = True
        self._c = ""
        self._c_accepted = False
        self._curr_lexeme = None
        self._pos = TextPos()

    @property
    def pos(self) ->TextPos:
        return self._pos

    @staticmethod
    def is_digit(c: str) -> bool:
        return c.isdigit()

    @staticmethod
    def is_hex_digit(c: str) -> bool:
        return c.isdigit() or c in Lexer.HEX_DIGITS

    @staticmethod
    def is_structural(c: str) -> bool:
        return c in Lexer.STRUCTURALS

    @staticmethod
    def is_whitespace(c: str) -> bool:
        return c in Lexer.WHITESPACES 
        # Two times faster than str.isspace()

    def handle_escaped_char(self, start: TextPos) -> str:
        value = ""
        for _i in range(0, 4):
            if not (self.next_char() and Lexer.is_hex_digit(self._c)):
                raise JSONParserError(start, JSONParserMessage.ERR_UNALLOWED_ESCAPE_SEQ)
            value += self._c
            self._c_accepted = True
        code = int(value, base = 16)
        return chr(code)
    
    def handle_literal(self) -> Lexeme:
        pos = self._pos.make_copy()
        value = self._c
        self._c_accepted = True
        while self.next_char():
            if self.is_whitespace(self._c) or self.is_structural(self._c):
                break
            value += self._c
            self._c_accepted = True
        if value == "false":
            return Lexeme(pos, Token.LITERAL_FALSE, value, literal_kind = LiteralTokenKind.LT_FALSE)
        elif value == "null":
            return Lexeme(pos, Token.LITERAL_NULL, value, literal_kind = LiteralTokenKind.LT_NULL)
        elif value == "true":
            return Lexeme(pos, Token.LITERAL_TRUE, value, literal_kind = LiteralTokenKind.LT_TRUE)
        else:
            raise JSONParserError(pos, JSONParserMessage.ERR_INVALID_LITERAL_FMT, value)

    def handle_number(self) -> Lexeme:
        pos = self._pos.make_copy()
        np = NumericParser()
        accepting = True
        while accepting:
            if np.read_char(self._c):
                self._c_accepted = True
                accepting = self.next_char()
            else:
                break
        tok = Token.UNKNOWN
        numeric_kind = NumericTokenKind.NT_UNKNOWN
        if np.type == NumericTokenKind.NT_DECIMAL:
            tok = Token.NUMBER_DECIMAL
            numeric_kind = NumericTokenKind.NT_DECIMAL
        elif np.type == NumericTokenKind.NT_FLOAT:
            tok = Token.NUMBER_FLOAT
            numeric_kind = NumericTokenKind.NT_FLOAT
        elif np.type == NumericTokenKind.NT_INTEGER:
            tok = Token.NUMBER_INT
            numeric_kind = NumericTokenKind.NT_INTEGER
        else:
            raise JSONParserError(self._pos, JSONParserMessage.ERR_INVALID_NUMBER)
        if self._c_accepted or self.is_whitespace(self._c) or self.is_structural(self._c):
            return Lexeme(pos, tok, np.value, numeric_kind = numeric_kind)
        else:
            raise JSONParserError(self._pos, JSONParserMessage.ERR_INVALID_NUMBER)

    def handle_string(self) -> Lexeme:
        start_pos = self._pos.make_copy()
        value = ""
        while self.next_char():
            if self._c == '"':
                self._c_accepted = True
                return Lexeme(start_pos, Token.STRING, value)
            elif self._c == '\\':
                pos = self._pos.make_copy()
                if not self.next_char():
                    raise JSONParserError(pos, JSONParserMessage.ERR_UNCLOSED_STRING)
                if esc_char := Lexer.ESCAPE_CHARS.get(self._c):
                    value += esc_char
                    self._c_accepted = True
                elif self._c == 'u':
                    value += self.handle_escaped_char(pos)
                else:
                    s = "\\" + self._c
                    raise JSONParserError(pos, JSONParserMessage.ERR_UNRECOGNIZED_ESCAPE_SEQ_FMT, s)
            else:
                value += self._c
                self._c_accepted = True
        raise JSONParserError(self._pos, JSONParserMessage.ERR_UNCLOSED_STRING)

    def next_char(self) -> bool:
        is_new_line = self._c == '\n'
        self._c = self._reader.read(1)
        self._eof = self._c == "" or self._c is None
        if not self._eof:
            self._c_accepted = False
            if is_new_line: 
                self._pos.newline()
            self._pos.col += 1
            return True
        return False
    
    def eof(self) -> bool:
        return self._eof

    def next_lexeme(self) -> Lexeme:
        if self._c_accepted or self._initial:
            if not self.next_char():
                return None
        self._initial = False
        self.skip_whitespaces()
        if not self._c_accepted:
            c = self._c
            pos = self._pos.make_copy()
            if c == '"':
                return self.handle_string()
            elif self._c in Lexer.DEC_DIGITS_S:
                return self.handle_number()
            elif tok := Lexer.STRUCTURALS.get(c):
                self._c_accepted = True
                return Lexeme(pos, tok, c)
            elif c in Lexer.LITERAL_PREFIXES:
                return self.handle_literal()
            else:
                raise JSONParserError(pos, JSONParserMessage.ERR_UNEXPECTED_CHAR_FMT, c)
        if self._eof:
            return None
        else:
            raise JSONParserError(self._pos, JSONParserMessage.ERR_UNEXPECTED_CHAR_FMT, self._c)

    def skip_whitespaces(self):
        while self.is_whitespace(self._c):
            self._c_accepted = True
            self.next_char()


class SAXHandlerIntf:
    def on_literal(self, kind: LiteralTokenKind, text: str):
        raise NotImplemented()
    def on_number(self, kind: NumericTokenKind, text: str):
        raise NotImplemented()
    def on_string(self, text: str):
        raise NotImplemented()
    def on_begin_object(self):
        raise NotImplemented()
    def on_member_name(self, text: str):
        raise NotImplemented()
    def on_end_object(self, member_count: int):
        raise NotImplemented()
    def on_begin_array(self):
        raise NotImplemented()
    def on_end_array(self, element_count: int):
        raise NotImplemented()
    def textpos_changed(self, pos: TextPos):
        raise NotImplemented()


class SAXParser:
    """
    JSON stream parser
    """

    def __init__(self, reader: io.TextIOBase, handler: SAXHandlerIntf) -> None:
        self._reader = reader
        self._handler = handler
        self._lexer = Lexer(self._reader)
        self._curr = Lexeme(TextPos())

    def _curr_token_is(self, tok: Token) -> bool:
        return self._curr_token() == tok

    def _curr_token_in(self, tokens: list) -> bool:
        for tok in tokens:
            if self._curr_token_is(tok):
                return True
        return False

    def next_lexeme(self) -> bool:
        self._curr = self._lexer.next_lexeme()
        if self._curr is not None:
            self._handler.textpos_changed(self._curr_pos().make_copy())
            return True
        return False
    
    def eof(self) -> bool:
        return self._lexer.eof()
    
    def _curr_pos(self) -> TextPos:
        return self._lexer.pos
    
    def _curr_text(self) -> str:
        return None if self._curr is None else self._curr.text
    
    def _curr_token(self) -> Token:
        return Token.UNKNOWN if self._curr is None else self._curr.token
    
    def run(self):
        self.parse_doc()

    def parse_doc(self):
        if self.next_lexeme():
            self.parse_value()
        elif self.eof():
            return # Empty doc
        self.next_lexeme()
        if not self.eof():
            if self.next_lexeme():
                raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_UNEXPECTED_LEXEME_FMT, self._curr_text())
            else:
                raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_EOF, self._curr_text())

    def parse_value(self):
        if self._curr_token_is(Token.BEGIN_ARRAY):
            self.parse_array()
        elif self._curr_token_is(Token.BEGIN_OBJECT):
            self.parse_object()
        elif self._curr_token_in([Token.LITERAL_FALSE, Token.LITERAL_NULL, Token.LITERAL_TRUE]):
            self.parse_literal()
        elif self._curr_token_in([Token.NUMBER_DECIMAL, Token.NUMBER_FLOAT, Token.NUMBER_INT]):
            self.parse_number()
        elif self._curr_token_is(Token.STRING):
            self.parse_string()
        else:
            raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_VALUE_BUT_FOUND_FMT, self._curr_text())

    def parse_array(self):
        if not self._curr_token_is(Token.BEGIN_ARRAY):
            raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_ARRAY)
        self._handler.on_begin_array()
        element_count = 0
        if self.next_lexeme() and not self._curr_token_is(Token.END_ARRAY):
            element_count = self.parse_array_items()
        if self._curr_token_is(Token.END_ARRAY):
            self._handler.on_end_array(element_count)
        else:
            raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_UNCLOSED_ARRAY)

    def parse_array_items(self) -> int:
        element_count = 0
        is_next_item = True
        while is_next_item:
            self.parse_value()
            element_count += 1;
            is_next_item = self.next_lexeme() and self._curr_token_is(Token.VALUE_SEPARATOR)
            if is_next_item and not self.next_lexeme():
                raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_ARRAY_ITEM)
        return element_count

    def parse_object(self):
        if not self._curr_token_is(Token.BEGIN_OBJECT):
            raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_OBJECT)
        start_pos = self._curr_pos().make_copy()
        self._handler.on_begin_object()
        member_count = 0
        if self.next_lexeme() and not self._curr_token_is(Token.END_OBJECT):
            member_count = self.parse_object_members()
        if self._curr_token_is(Token.END_OBJECT):
            self._handler.on_end_object(member_count)
        else:
            raise JSONParserError(start_pos, JSONParserMessage.ERR_UNCLOSED_OBJECT)

    def parse_object_members(self) -> int:
        member_count = 0
        is_next_member = True
        while is_next_member:
            if not self._curr_token_is(Token.STRING):
                raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_MEMBER_NAME)
            self._handler.on_member_name(self._curr_text())
            member_count += 1
            if not self.next_lexeme() or not self._curr_token_is(Token.NAME_SEPARATOR):
                raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_NAME_SEPARATOR)
            if not self.next_lexeme():
                raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_VALUE)
            self.parse_value()
            is_next_member = self.next_lexeme() and self._curr_token_is(Token.VALUE_SEPARATOR)
            if is_next_member and not self.next_lexeme():
                raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_MEMBER_NAME)
        return member_count

    def parse_literal(self):
        if Token.is_literal_token(self._curr_token()):
            self._handler.on_literal(self._curr.literal_kind, self._curr_text())
        else:
            raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_LITERAL)

    def parse_number(self):
        if self._curr_token_in([Token.NUMBER_DECIMAL, Token.NUMBER_FLOAT]):
            self._handler.on_number(NumericTokenKind.NT_FLOAT, self._curr_text())
        elif self._curr_token_is(Token.NUMBER_INT):
            self._handler.on_number(NumericTokenKind.NT_INTEGER, self._curr_text())
        else:
            raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_NUMBER)

    def parse_string(self):
        if self._curr_token_is(Token.STRING):
            self._handler.on_string(self._curr_text())
        else:
            raise JSONParserError(self._curr_pos(), JSONParserMessage.ERR_EXPECTED_STRING)

#
# SAX handler basic implementation
#
class SimpleStack:
    def __init__(self) -> None:
        self._data = list()

    def top(self) -> any:
        return self._data[-1]
   
    def pop(self) -> any:
        return self._data.pop()
    
    def push(self, item):
        self._data.append(item)

    @property
    def size(self) -> int:
        return len(self._data)

class SAXHandlerBasic(SAXHandlerIntf):

    def __init__(self) -> None:
        self._stack = SimpleStack()

    @property
    def result(self) -> any:
        if self._stack.size == 0:
            return None
        elif self._stack.size == 1:
            return self._stack.pop()
        raise JSONError(f"Unexpected stack size: {self._stack.size}")
    
    def on_literal(self, kind: LiteralTokenKind, text: str):
        if kind == LiteralTokenKind.LT_FALSE:
            self._stack.push(False)
        elif kind == LiteralTokenKind.LT_TRUE:
            self._stack.push(True)
        elif kind == LiteralTokenKind.LT_NULL:
            self._stack.push(None)
        else:
            raise JSONError(f"Unsupported literal kind: {str(kind)}. Value: {text}")

    def on_number(self, kind: NumericTokenKind, text: str):
        if kind == NumericTokenKind.NT_INTEGER:
            self._stack.push(int(text))
        elif kind in [NumericTokenKind.NT_DECIMAL, NumericTokenKind.NT_FLOAT]:
            self._stack.push(float(text))
        else:
            raise JSONError(f"Unsupported number kind: {str(kind)}. Value: {text}")

    def on_string(self, text: str):
        self._stack.push(text)

    def on_begin_object(self):
        pass

    def on_member_name(self, text: str):
        self._stack.push(text)

    def on_end_object(self, member_count: int): 
        member_item_count = member_count * 2  # Two items per member: name and value
        if member_item_count > self._stack.size:
            raise JSONError(f"Element count {member_item_count} is greater than stack size {self._stack.size}")
        obj = {}
        for _i in range(member_count):
            value = self._stack.pop()
            name = self._stack.pop()
            obj[name] = value
        self._stack.push(obj)

    def on_begin_array(self):
        pass

    def on_end_array(self, element_count: int):
        if element_count > self._stack.size:
            raise JSONError(f"Element count {element_count} is greater than stack size {self._stack.size}")
        array = []
        for _i in range(element_count):
            array.insert(0, self._stack.pop())
        self._stack.push(array)

    def textpos_changed(self, pos: TextPos):
        pass
