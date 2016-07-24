# coding: utf-8

import unittest

import sys

from pprint import pprint
from serialize import (Attr, AttrObject, AbstractAttrObject, IntegerAttr,
                       FloatAttr, MappingFailedError, UnicodeAttr,
                       ChoiceAttr, StringChoiceAttr, BytesAttr, OptionalAttr,
                       ConstantAttr, NoneableAttr, DatetimeAttr, _all_subclasses)

class TestAllSubclasses(unittest.TestCase):
    def runTest(self):
        class A(object): pass
        class B(A): pass
        class C(A): pass
        class D(B): pass
        class E(C): pass
        class F(D, E): pass

        self.assertEqual(
            sorted(list(_all_subclasses(A))),
            sorted([A, B, C, D, E, F])
        )



class TestPostinitLink(unittest.TestCase):
    def test_if_postinit_is_unextendedible(self):
        N = []
        class Parent(AttrObject):
            def __postinit__(self):
                N.append(1)

        class Child(Parent):
            pass

        Child()
        self.assertEqual(len(N), 1)

    def test_three_postinit_seq(self):
        seq = []
        class Grandparent(AttrObject):
            def __postinit__(self):
                seq.append(1)

        class Parent(Grandparent):
            def __postinit__(self):
                seq.append(2)

        class Child(Parent):
            def __postinit__(self):
                seq.append(3)

        Child()
        self.assertEqual(seq, [1, 2, 3])
    
    def test_postinit_hole(self):
        seq = []
        class Grandparent(AttrObject):
            def __postinit__(self):
                seq.append(1)

        class Parent(Grandparent):
            pass

        class Child(Parent):
            def __postinit__(self):
                seq.append(3)

        Child()
        self.assertEqual(seq, [1, 3])

    def test_diamond_of_death(self):
        seq = []
        class Grandparent(AttrObject):
            def __postinit__(self):
                seq.append(0)

        class ParentA(Grandparent):
            def __postinit__(self):
                seq.append(1)
            
        class ParentB(Grandparent):
            def __postinit__(self):
                seq.append(1)
            
        class Child(ParentA, ParentB):
            def __postinit__(self):
                seq.append(2)
        Child()
        self.assertEqual(seq, [0, 1, 1, 2])
        


class TestSimplest(unittest.TestCase):
    class EmptyClass(AttrObject):
        attributes = {}

    class SimpleClass(AttrObject):
        attributes = {
            "price": IntegerAttr(),
            "percentage": FloatAttr(),
        }

    def test_empty(self):
        self.EmptyClass.loads_dict({})

        with self.assertRaises(MappingFailedError):
            self.SimpleClass.loads_dict({})

    def test_invalid_dict(self):
        with self.assertRaises(MappingFailedError):
            self.EmptyClass.loads_dict([])

    def test_simplest(self):
        x = self.SimpleClass.loads_dict({
            "price": 213123,
            "percentage": 43.0
        })
        self.assertEqual(x.price, 213123)
        self.assertEqual(x.percentage, 43.0)

        with self.assertRaises(MappingFailedError):
            self.SimpleClass.loads_dict({
                "price": 3.14,
                "percentage": 43.0
            })

    def test_missing_keyvalue(self):
        with self.assertRaises(MappingFailedError):
            self.SimpleClass.loads_dict({
                "price": 3
            })

class TestShorthandNumber(unittest.TestCase):
    class NumberShortHand(AttrObject):
        attributes = {
            "int_var": int,
            "long_var": long,
            "float_var": float
        }


    def test_number(self):
        self.NumberShortHand.loads_dict({
            "int_var": 2,
            "long_var": 3L,
            "float_var": 5.0
        })

        # Long and Integer are interchangable
        # A float attribute can be given an integer
        self.assertIsInstance(self.NumberShortHand.type_signature()["float_var"],
                              FloatAttr)

        x = self.NumberShortHand.loads_dict({
            "int_var": 3L,
            "long_var": 1,
            "float_var": 5
        })
        # But in that case, they should be coerced to float numbers
        self.assertEqual(x.float_var, 5.0)
        self.assertEqual(type(x.float_var), float)


class TestString(unittest.TestCase):
    LOVE_CJK_UNICODE = u'愛'
    CLOTH_HANGUL_UTF8 = b'옷'
    LOVE_HIRA_UTF8 = b'あい'

    class StrClass(AttrObject):
        attributes = {
            "love": UnicodeAttr(encoding="utf-8"),
            "cloth": BytesAttr(encoding="utf-8")
        }

    def test_typecheck(self):
        with self.assertRaises(MappingFailedError):
            self.StrClass.loads_dict({
                "love": 1,
                "cloth": 2
            })


    def test_unicode(self):
        x = self.StrClass.loads_dict({
            "love": self.LOVE_CJK_UNICODE,
            "cloth": self.CLOTH_HANGUL_UTF8
        })
        self.assertEqual(x.love, self.LOVE_CJK_UNICODE)
        self.assertEqual(x.cloth, self.CLOTH_HANGUL_UTF8)

        self.assertEqual(type(x.love), unicode)
        self.assertEqual(type(x.cloth), bytes)

    def test_auto_encoding(self):
        x = self.StrClass.loads_dict({
            "love": self.LOVE_CJK_UNICODE.encode("utf-8"),
            "cloth": self.CLOTH_HANGUL_UTF8.decode("utf-8")
        })

        self.assertEqual(x.love, self.LOVE_CJK_UNICODE)
        self.assertEqual(x.cloth, self.CLOTH_HANGUL_UTF8)

        self.assertEqual(type(x.love), unicode)
        self.assertEqual(type(x.cloth), bytes)

        d = x.dumps_dict()
        self.assertEqual(d, {"love": self.LOVE_CJK_UNICODE, "cloth": self.CLOTH_HANGUL_UTF8})

    
    class StrAsciiClass(AttrObject):
        attributes = {
            "love": UnicodeAttr(encoding="ascii"),
            "shorthand": unicode
        }

    def test_ascii(self):
        x = self.StrAsciiClass.loads_dict({
            "love": "Love",
            "shorthand": self.LOVE_HIRA_UTF8
        })

        with self.assertRaises(MappingFailedError):
            self.StrAsciiClass.loads_dict({
                "love": self.LOVE_HIRA_UTF8,
                "shorthand": self.LOVE_HIRA_UTF8
            })
    


class TestOptional(unittest.TestCase):
    class OptionalClass(AttrObject):
        attributes = {
            "name": OptionalAttr(unicode)
        }


    class OptionalNumberClass(AttrObject):
        attributes = {
            "option": OptionalAttr(int, default=0)
        }

    def test_optional_str(self):
        with self.assertRaises(MappingFailedError):
            x = self.OptionalClass.loads_dict({"name": 119})

        with self.assertRaises(MappingFailedError):
            self.OptionalClass.loads_dict({"name": None})

        self.OptionalClass.loads_dict({"name": "Johnson"})
        y = self.OptionalClass.loads_dict({})
        self.assertIsNone(y.name)
        y.dumps_dict()

    
    def test_optional_number(self):
        x = self.OptionalNumberClass.loads_dict({})
        self.assertEquals(x.option, 0)

        y = self.OptionalNumberClass.loads_dict({
            "option": 2
        })

        self.assertEquals(y.option, 2)
        
        with self.assertRaises(MappingFailedError) as comm:
            # None is not allowed for value in the following case
            z = self.OptionalNumberClass.loads_dict({
                "option": None
            })


class TestNoneable(unittest.TestCase):
    class NoneableClass(AttrObject):
        attributes = {
            "opt": NoneableAttr(int)
        }

    def runTest(self):
        with self.assertRaises(MappingFailedError):
            self.NoneableClass.loads_dict({})
        with self.assertRaises(MappingFailedError):
            self.NoneableClass.loads_dict({"opt": "A"})

        self.assertEquals(self.NoneableClass.loads_dict({"opt": 2}).dumps_dict(),
                          {"opt": 2})

        self.assertEquals(self.NoneableClass.loads_dict({"opt": None}).opt,
                          None)



class TestList(unittest.TestCase):
    class ListClass(AttrObject):
        attributes = {
            "int_list": OptionalAttr([int]),
            "int_unicode_list": OptionalAttr([int, unicode]),
        }

    def runTest(self):
        x = [1, 2, 3]
        self.assertEqual(
            self.ListClass.loads_dict({"int_list": [1, 2, 3, 4]}).dumps_dict()["int_list"],
            [1, 2, 3, 4]
        )
        self.ListClass.loads_dict({"int_unicode_list": [1, "A", 3]})
        self.ListClass.loads_dict({"int_unicode_list": [1, "A", 3, "B"]})

        with self.assertRaises(MappingFailedError):
            self.ListClass.loads_dict({"int_unicode_list": [1, "A", 3, 4]})
        
    
class TestSignatureDict(unittest.TestCase):
    class SimpleAPIHeader(AttrObject):
        attributes = {
            "success": OptionalAttr(bool, default=True),
            "error_details": OptionalAttr(
                [{
                    "level": StringChoiceAttr(["fatal", "error", "warning", "info"]),
                    "message": OptionalAttr(unicode, default=u"")
                }],
                default=list # default factory
            )
        }

    def test_default(self):
        header = self.SimpleAPIHeader()
        self.assertEqual(header.dumps_dict(), {"success": True, "error_details": []})

    def test_simple_failure_message(self):
        header = self.SimpleAPIHeader(
            success=False,
            error_details=[{
                "level": u"warning"
            }]
        )
        self.assertEqual(
            header.dumps_dict(),
            {
                "success": False,
                "error_details": [{
                    "level": u"warning",
                    "message": u""
                }]
            }
        )

    def test_invalid_choice(self):
        with self.assertRaises(MappingFailedError):
            self.SimpleAPIHeader(
                success=False,
                error_details=[{
                    "level": u"SPARTAAAAA"
                }]
            )

    def test_multiple_details(self):
        header = self.SimpleAPIHeader(
            success=False,
            error_details=[{
                "level": u"warning",
                "message": "1"
            }, {
                "level": u"info",
                "message": "2"
            }, {
                "level": u"fatal",
                "message": "3"
            }]
        )

        self.assertEqual(header.dumps_dict(), {
            "success": False,
            "error_details": [{
                "level": u"warning",
                "message": "1"
            }, {
                "level": u"info",
                "message": "2"
            }, {
                "level": u"fatal",
                "message": "3"
            }]
        })


class TestLiteral(unittest.TestCase):
    def _get_attributes(self):
        return {
            "integer": 1,
            "boolean": True,
            "none": None,
            "bytes": b"bytes",
            "unicode": u"uni",
            "float": 3.14159265,
        }

    def _make_class(self, wrong_idx=-1):
        attributes = self._get_attributes()
        for idx, key in zip(range(len(attributes)), sorted(attributes.keys())):
            if idx == wrong_idx:
                attributes[key] = {"KABOOM": True}
                break
        _attrs = attributes
        class CLS(AttrObject):
            attributes = _attrs

        return CLS

    def runTest(self):
        self._make_class().loads_dict(self._get_attributes())

        for idx in range(6):
            with self.assertRaises(MappingFailedError):
                self._make_class(idx).loads_dict(self._get_attributes())



class TestInvalidAttr(unittest.TestCase):
    def test_not_attr_object(self):
        with self.assertRaises(TypeError):
            class A(AttrObject):
                class Employee(object):
                    pass
                attributes = {
                    "A": Employee
                }
            # force evalution of signature
            A.type_signature()
    

class TestSimpleClassRef(unittest.TestCase):
    def test_simple_ref(self):
        class Employee(AttrObject):
            attributes = {
                "name": unicode,
                "gender": ChoiceAttr(["male", 'female'])
            }

        class Company(AttrObject):
            attributes = {
                "employees": [Employee],
                "CEO": Employee,
            }

        company = Company(
            CEO=Employee(
                name="Ritchie",
                gender="male"
            ),
            employees=[Employee(
                name="Dave",
                gender="male"
            ), Employee(
                name="Taylor",
                gender="female"
            )]
        )

        self.assertEqual( 
            company.to_dict(),
            {'CEO': {'gender': 'male', 'name': u'Ritchie'}, 'employees': [{'gender': 'male', 'name': u'Dave'}, {'gender': 'female', 'name': u'Taylor'}]}
        )

class TestConstantOverridingAttr(unittest.TestCase):
    def runTest(self):
        class Action(AttrObject):
            attributes = {
                "name": unicode
            }

        class ActionList(Action):
            attributes = {
                "name": ConstantAttr(u"cmdlist"), # overriding
                "extra": OptionalAttr(None, default=None)
            }

        with self.assertRaises(MappingFailedError):
            Action() # name is not given

        self.assertEqual(ActionList().name, "cmdlist")
        self.assertEqual(ActionList(name="ConstantAttr ignores given argument").name, 
                         "cmdlist")

        self.assertEqual(sorted(ActionList.type_signature().keys()),
                         sorted(["name", "extra"]))


class TestAbstractClass(unittest.TestCase):
    def runTest(self):
        class Player(AbstractAttrObject):
            attributes = {
                "hp": int
            }

        class Action(AbstractAttrObject):
            attributes = {
                "name": unicode
            }

            def run(self, player):
                raise NotImplementedError

        class ActionList(Action):
            attributes = {
                "name": ConstantAttr(u"cmdlist"), # overriding
                "*list": [Action]
            }

            def run(self, player):
                for action in self.list:
                    action.run(player)

        class DamageAction(Action):
            attributes = {
                "damage": int
            }

            def run(self, player):
                player.hp -= self.damage


        class HealAction(Action):
            attributes = {
                "heal": int
            }

            def run(self, player):
                player.hp += self.heal

        player = Player(hp=100)
        action = ActionList(
            DamageAction(name="DamageA", damage=10),
            ActionList(
                DamageAction(name="DamageB", damage=20),
                DamageAction(name="DamageC", damage=30),
            ),
            HealAction(name="HealingA", heal=5)
        )
        action.run(player)
        self.assertEqual(player.to_dict()["hp"], 45)

        d = action.dumps_dict()
        loaded_action = Action.loads_dict(d)
        self.assertEqual(action, loaded_action)


class TestJSONDatetime(unittest.TestCase):
    def runTest(self):
        from datetime import datetime

        class Clock(AttrObject):
            attributes = {
                "date": DatetimeAttr(format="%Y-%m-%d")
            }


        clock = Clock(date="2016-01-01")
        self.assertEqual(clock.date.strftime("%Y-%m-%d"), "2016-01-01")

        self.assertIsInstance(clock.to_dict()["date"], datetime)
        self.assertEqual(clock.to_json_dict()["date"], "2016-01-01")




