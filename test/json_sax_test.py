#!/usr/bin/env python3

#-------------------------------------------------------------------#
# Copyright (C) 2019-2023 by Serguei Tarassov <serge@arbinada.com>  #
# Distributed freely under the MIT License                          #
#-------------------------------------------------------------------#

"""
Tests of JSON stream (SAX) parser
"""

import io
import sys
import os
import unittest

sys.path.append(os.path.realpath(os.path.join(os.path.dirname(__file__), "..")))
from json_sax import TextPos, Token, Lexeme, Lexer, JSONParserError, JSONParserMessage, \
    SAXHandlerBasic, SAXParser


class JsonLexerTest(unittest.TestCase):

    def _compare_lexemes(self, expected: Lexeme, lex: Lexeme, title: str):
        title += ": "
        self.assertEqual(expected.token, lex.token, title + "expected token: " + str(expected.token) + ", got: " + str(lex.token))
        self.assertEqual(expected.pos, lex.pos, title + "expected: " + str(expected.pos) + " got: " + str(lex.pos))
        self.assertEqual(expected.text, lex.text, title + "text")

    def _check_lexeme(self, input: str, expected: Lexeme, title: str):
        reader = io.StringIO(input)
        lexer  = Lexer(reader)
        lex = lexer.next_lexeme()
        self.assertIsNotNone(lex, title + ": next_lexeme() failed with no errors")
        self._compare_lexemes(expected, lex, title)

    def _check_error(self, input: str, msg_id: int, pos: TextPos, title: str):
        title2 = title + ": "
        reader = io.StringIO(input)
        lexer  = Lexer(reader)
        caught_error = False
        try:
            while lexer.next_lexeme():
                pass
        except JSONParserError as ex:
            caught_error = True
            self.assertTrue(ex.msg_id == msg_id, title2 + f"origin. {str(ex)}")
            self.assertTrue(str(ex) != "" , title2 + "text is empty")
            self.assertEqual(pos, ex.pos, title2 + f"error pos. {str(ex)}")
        self.assertTrue(caught_error, title2 + "no errors")

    def _check_text(self, input: str, expected: list, title: str):
        reader = io.StringIO(input)
        lexer  = Lexer(reader)
        title2 = title + ": "
        i = 0;
        lex = None
        while True:
            lex = lexer.next_lexeme()
            if lex is None:
                break
            self.assertTrue(i < len(expected), title2 + f"lex count {i + 1} exceeds expected one {len(expected)}")
            expected_lex = expected[i]
            self._compare_lexemes(expected_lex, lex, f"{title} lexeme[{i}]")
            i += 1
        self.assertEqual(len(expected), i, title2 + "lex count")

    def test_empty_streams(self):
        input = None
        reader = io.StringIO(input)
        lexer  = Lexer(reader)
        self.assertIsNone(lexer.next_lexeme())

    def test_simple_tokens(self):
        self._check_lexeme("[", Lexeme(TextPos(1, 1), Token.BEGIN_ARRAY, "["), "Begin array 1.1")
        self._check_lexeme(" \t[", Lexeme(TextPos(1, 3), Token.BEGIN_ARRAY, "["), "Begin array 1.2")
        self._check_lexeme("\r\n[", Lexeme(TextPos(2, 1), Token.BEGIN_ARRAY, "["), "Begin array 1.3")
        self._check_lexeme(" \t\r\n[", Lexeme(TextPos(2, 1), Token.BEGIN_ARRAY, "["), "Begin array 1.4")
        self._check_lexeme(" \t\r\n \t[", Lexeme(TextPos(2, 3), Token.BEGIN_ARRAY, "["), "Begin array 1.5")
        self._check_lexeme("\r\n\r\n\t[", Lexeme(TextPos(3, 2), Token.BEGIN_ARRAY, "["), "Begin array 1.6")
        self._check_lexeme("\n[", Lexeme(TextPos(2, 1), Token.BEGIN_ARRAY, "["), "Begin array 1.7")
        self._check_lexeme("{", Lexeme(TextPos(1, 1), Token.BEGIN_OBJECT, "{"), "Begin object 1.1")
        self._check_lexeme("]", Lexeme(TextPos(1, 1), Token.END_ARRAY, "]"), "End array 1.1")
        self._check_lexeme("}", Lexeme(TextPos(1, 1), Token.END_OBJECT, "}"), "End object 1.1")
        self._check_lexeme("false", Lexeme(TextPos(1, 1), Token.LITERAL_FALSE, "false"), "Literal 1.1")
        self._check_lexeme("null", Lexeme(TextPos(1, 1), Token.LITERAL_NULL, "null"), "Literal 2.1")
        self._check_lexeme("true", Lexeme(TextPos(1, 1), Token.LITERAL_TRUE, "true"), "Literal 3.1")
        self._check_lexeme(":", Lexeme(TextPos(1, 1), Token.NAME_SEPARATOR, ":"), "Name separator 1.1")
        self._check_lexeme(",", Lexeme(TextPos(1, 1), Token.VALUE_SEPARATOR, ","), "Value separator 1.1")

    def test_strings(self):
        self._check_lexeme("\"Hello world!\"", Lexeme(TextPos(1, 1), Token.STRING, "Hello world!"), "String 1")
        self._check_lexeme("\"\\\"\"", Lexeme(TextPos(1, 1), Token.STRING, "\""), "String 2.1")
        self._check_lexeme("\"\\\\\"", Lexeme(TextPos(1, 1), Token.STRING, "\\"), "String 2.2")
        self._check_lexeme("\"\\/\"", Lexeme(TextPos(1, 1), Token.STRING, "/"), "String 2.3")
        self._check_lexeme("\"\\b\"", Lexeme(TextPos(1, 1), Token.STRING, "\b"), "String 2.4")
        self._check_lexeme("\"\\f\"", Lexeme(TextPos(1, 1), Token.STRING, "\f"), "String 2.5")
        self._check_lexeme("\"\\n\"", Lexeme(TextPos(1, 1), Token.STRING, "\n"), "String 2.6")
        self._check_lexeme("\"\\r\"", Lexeme(TextPos(1, 1), Token.STRING, "\r"), "String 2.7")
        self._check_lexeme("\"\\t\"", Lexeme(TextPos(1, 1), Token.STRING, "\t"), "String 2.8")
        self._check_lexeme("\"-\\\"-\\\\-\\/-\\b-\\f-\\n-\\r-\\t-\"", Lexeme(TextPos(1, 1), Token.STRING, "-\"-\\-/-\b-\f-\n-\r-\t-"), "String 2.9")
        self._check_lexeme("\"Строка déjà\"", Lexeme(TextPos(1, 1), Token.STRING, "Строка déjà"), "String 3.3")
        self._check_lexeme("\"\b\"", Lexeme(TextPos(1, 1), Token.STRING, "\b"), "String 3.4")

    def test_escape_sequences(self):
        self._check_lexeme("\"\\u1234\"", Lexeme(TextPos(1, 1), Token.STRING, "\u1234"), "ESC 1.1")
        self._check_lexeme("\"\\u0022\"", Lexeme(TextPos(1, 1), Token.STRING, "\u0022"), "ESC 1.2")
        self._check_lexeme("\"\\u00ff\"", Lexeme(TextPos(1, 1), Token.STRING, "\u00ff"), "ESC 1.3")
        self._check_lexeme("\"Abc\\u1234Def\"", Lexeme(TextPos(1, 1), Token.STRING, "Abc\u1234""Def"), "ESC 2.2")


    def test_numbers(self):
        self._check_lexeme("12345", Lexeme(TextPos(1, 1), Token.NUMBER_INT, "12345"), "Num 1.1")
        self._check_lexeme("-12345", Lexeme(TextPos(1, 1), Token.NUMBER_INT, "-12345"), "Num 1.2")
        self._check_lexeme("123.456", Lexeme(TextPos(1, 1), Token.NUMBER_DECIMAL, "123.456"), "Num 2.1")
        self._check_lexeme("-123.456", Lexeme(TextPos(1, 1), Token.NUMBER_DECIMAL, "-123.456"), "Num 2.2")
        self._check_lexeme("1.23456E10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "1.23456E10"), "Num 3.1")
        self._check_lexeme("1.23456e10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "1.23456e10"), "Num 3.2")
        self._check_lexeme("1.23456E+10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "1.23456E+10"), "Num 3.11")
        self._check_lexeme("1.23456e+10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "1.23456e+10"), "Num 3.21")
        self._check_lexeme("-1.23456E10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "-1.23456E10"), "Num 3.3")
        self._check_lexeme("-1.23456e10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "-1.23456e10"), "Num 3.4")
        self._check_lexeme("1.23456E-10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "1.23456E-10"), "Num 3.5")
        self._check_lexeme("1.23456e-10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "1.23456e-10"), "Num 3.6")
        self._check_lexeme("-1.23456E-10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "-1.23456E-10"), "Num 3.7")
        self._check_lexeme("-1.23456e-10", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "-1.23456e-10"), "Num 3.8")
        self._check_lexeme("0", Lexeme(TextPos(1, 1), Token.NUMBER_INT, "0"), "Num 4.1")
        self._check_lexeme("-0", Lexeme(TextPos(1, 1), Token.NUMBER_INT, "-0"), "Num 4.2")
        self._check_lexeme("0.0", Lexeme(TextPos(1, 1), Token.NUMBER_DECIMAL, "0.0"), "Num 4.3")
        self._check_lexeme("-0.0", Lexeme(TextPos(1, 1), Token.NUMBER_DECIMAL, "-0.0"), "Num 4.4")
        self._check_lexeme("0.0e0", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "0.0e0"), "Num 4.5")
        self._check_lexeme("-0.0e-0", Lexeme(TextPos(1, 1), Token.NUMBER_FLOAT, "-0.0e-0"), "Num 4.6")

    def test_texts(self):
        self._check_text("", [], "Test 1")
        self._check_text(
            "\n[\n]\n", 
            [
                Lexeme(TextPos(2, 1), Token.BEGIN_ARRAY, "["),
                Lexeme(TextPos(3, 1), Token.END_ARRAY, "]")
            ],
            "Test 2")
        self._check_text(
            "[]\n{}\nfalse null true\n\"Name 1\":\"Value 1\",", 
            [
                Lexeme(TextPos(1, 1), Token.BEGIN_ARRAY, "["),
                Lexeme(TextPos(1, 2), Token.END_ARRAY, "]"),
                Lexeme(TextPos(2, 1), Token.BEGIN_OBJECT, "{"),
                Lexeme(TextPos(2, 2), Token.END_OBJECT, "}"),
                Lexeme(TextPos(3, 1), Token.LITERAL_FALSE, "false"),
                Lexeme(TextPos(3, 7), Token.LITERAL_NULL, "null"),
                Lexeme(TextPos(3, 12), Token.LITERAL_TRUE, "true"),
                Lexeme(TextPos(4, 1), Token.STRING, "Name 1"),
                Lexeme(TextPos(4, 9), Token.NAME_SEPARATOR, ":"),
                Lexeme(TextPos(4, 10), Token.STRING, "Value 1"),
                Lexeme(TextPos(4, 19), Token.VALUE_SEPARATOR, ",")
            ],
            "Test 3")
        self._check_text(
            "[-4.54557e+18]", 
            [
                Lexeme(TextPos(1, 1), Token.BEGIN_ARRAY, "["),
                Lexeme(TextPos(1, 2), Token.NUMBER_FLOAT, "-4.54557e+18"),
                Lexeme(TextPos(1, 14), Token.END_ARRAY, "]")
            ],
            "Test 4")
        self._check_text(
            "{\t\"abc def\": -4.54557e+18 }", 
            [
                Lexeme(TextPos(1, 1), Token.BEGIN_OBJECT, "{"),
                Lexeme(TextPos(1, 3), Token.STRING, "abc def"),
                Lexeme(TextPos(1, 12), Token.NAME_SEPARATOR, ":"),
                Lexeme(TextPos(1, 14), Token.NUMBER_FLOAT, "-4.54557e+18"),
                Lexeme(TextPos(1, 27), Token.END_OBJECT, "}")
            ],
            "Test 5")

    def test_lexer_errors(self):
        self._check_error("try", JSONParserMessage.ERR_INVALID_LITERAL_FMT, TextPos(1, 1), "E1010.1")
        self._check_error("\ntrue2", JSONParserMessage.ERR_INVALID_LITERAL_FMT, TextPos(2, 1), "E1010.2")
        self._check_error("true\ntrue2", JSONParserMessage.ERR_INVALID_LITERAL_FMT, TextPos(2, 1), "E1010.3")
        self._check_error("null\nnulltrue", JSONParserMessage.ERR_INVALID_LITERAL_FMT, TextPos(2, 1), "E1010.4")
        self._check_error("false\nfalsetrue", JSONParserMessage.ERR_INVALID_LITERAL_FMT, TextPos(2, 1), "E1010.5")
        #
        self._check_error("-", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 1), "E1012.1")
        self._check_error("-.", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 2), "E1012.2")
        self._check_error("123.", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 4), "E1012.3")
        self._check_error("123.\"", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 5), "E1012.4.1")
        self._check_error("123.0\"", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 6), "E1012.4.2")
        self._check_error("1e", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 2), "E1012.5")
        self._check_error("1eA", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 3), "E1012.6")
        self._check_error("1e-1A", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 5), "E1012.7")
        self._check_error("00", JSONParserMessage.ERR_INVALID_NUMBER, TextPos(1, 2), "E1012.8")
        #
        self._check_error("\"\\u123\"", JSONParserMessage.ERR_UNALLOWED_ESCAPE_SEQ, TextPos(1, 2), "E1040.1")
        self._check_error("\"\\u123H\"", JSONParserMessage.ERR_UNALLOWED_ESCAPE_SEQ, TextPos(1, 2), "E1040.2")
        self._check_error("\"\\uABCD\\u123H\"", JSONParserMessage.ERR_UNALLOWED_ESCAPE_SEQ, TextPos(1, 8), "E1040.3")
        #
        self._check_error("\"", JSONParserMessage.ERR_UNCLOSED_STRING, TextPos(1, 1), "E1050.1")
        self._check_error("\"Hello", JSONParserMessage.ERR_UNCLOSED_STRING, TextPos(1, 6), "E1050.2")
        self._check_error("\"Hello\\n", JSONParserMessage.ERR_UNCLOSED_STRING, TextPos(1, 8), "E1050.3")
        self._check_error("\"Hello\\\"", JSONParserMessage.ERR_UNCLOSED_STRING, TextPos(1, 8), "E1050.4")
        #
        self._check_error("\t\b", JSONParserMessage.ERR_UNEXPECTED_CHAR_FMT, TextPos(1, 2), "E1060.1")
        self._check_error("[\x02]", JSONParserMessage.ERR_UNEXPECTED_CHAR_FMT, TextPos(1, 2), "E1060.2")
        #
        self._check_error("\"\\x", JSONParserMessage.ERR_UNRECOGNIZED_ESCAPE_SEQ_FMT, TextPos(1, 2), "E1070.1")


class SAXParserTest(unittest.TestCase):

    def _check_json(self, text: str, expected, title: str):
        reader = io.StringIO(text)
        handler = SAXHandlerBasic()
        parser = SAXParser(reader, handler)
        parser.run()
        result = handler.result
        self.assertEqual(type(result), type(expected))
        if isinstance(result, list):
            self.assertListEqual(result, expected)
        elif isinstance(result, dict):
            self.assertDictEqual(result, expected)
        else:
            self.assertEqual(result, expected)
    
    def test_empty_stream(self):
        self._check_json("", None, "Literals 1")

    def test_values_literals(self):
        self._check_json("true", True, "Literals 1")
        self._check_json("false", False, "Literals 2")
        self._check_json("null", None, "Literals 3")

    def test_values_numbers(self):
        self._check_json("123", 123, "Numeric 1")
        self._check_json("123.456", 123.456, "Numeric 2")
        self._check_json("1.23456e+08", 1.23456e+08, "Numeric 3")

    def test_values_strings(self):
        self._check_json("\"Hello world!\"", "Hello world!", "String 1")
        self._check_json("\"\\\"\"", "\"", "String 2.1")
        self._check_json("\"\\\\\"", "\\", "String 2.2")
        self._check_json("\"\\/\"", "/", "String 2.3")
        self._check_json("\"\\b\"", "\b", "String 2.4")
        self._check_json("\"\\f\"", "\f", "String 2.5")
        self._check_json("\"\\n\"", "\n", "String 2.6")
        self._check_json("\"\\r\"", "\r", "String 2.7")
        self._check_json("\"\\t\"", "\t", "String 2.8")
        self._check_json("\"-\\\"-\\\\-\\/-\\b-\\f-\\n-\\r-\\t-\"", "-\"-\\-/-\b-\f-\n-\r-\t-", "String 2.9")
        self._check_json("\"Строка déjà\"", "Строка déjà", "String 3.3")

    def test_values_escape_sequences(self):
        self._check_json("\"\\u1234\"", "\u1234", "ESC 1.1")
        self._check_json("\"\\u0022\"", "\u0022", "ESC 1.2")
        self._check_json("\"\\u00ff\"", "\u00ff", "ESC 1.3")
        self._check_json("\"Abc\\u1234Def\"", "Abc\u1234""Def", "ESC 2.2")

    def test_arrays(self):
        self._check_json("[]", [], "Array 1.1")
        self._check_json("[1, 2, 3]", [1, 2, 3], "Array 2.1")
        self._check_json("[1, 2, [3, 4]]", [1, 2, [3, 4]], "Array 3.1")

    def test_objects(self):
        self._check_json("{}", {}, "Obj 1.1")
        self._check_json(
            "{\"Prop 1\": 123, \"Prop 2\": true, \"Prop 3\": \"Str value\"}",
            {"Prop 1": 123, "Prop 2": True, "Prop 3": "Str value"},
            "Obj 2.1")
        self._check_json(
            "{\"Prop 1\": [1, 2, 3], \"Prop 2\": {\"Prop 2.1\": true}, \"Prop 3\": \"Str value\"}",
            {"Prop 1": [1, 2, 3], "Prop 2": {"Prop 2.1": True}, "Prop 3": "Str value"},
            "Obj 3.1")


if __name__ == "__main__":
    unittest.main()
