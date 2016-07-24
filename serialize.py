# coding: utf-8
u'''
Copyright (c) 2016 Alchan Kim

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
'''

import re
import json
import inspect

from datetime import datetime, time
from itertools import chain as chain_iters, cycle, izip
from operator import isCallable
from collections import Iterable, deque
from functools import partial

from parse import AttributeSignature


def _all_subclasses(cls):
    u'cls 자신을 포함한 모든 subclass들의 generator를 리턴한다.'
    already_yielded = set([])
    def inner(subcls):
        if subcls in already_yielded or subcls == type:
            return
        already_yielded.add(subcls)
        yield subcls

        for subsubcls in subcls.__subclasses__():
            for c in inner(subsubcls):
                yield c
    try:
        return inner(cls)
    except AttributeError as exc:
        raise AttributeError("AttributeError(%s) has been raised. Isn't your class derived from the 'object' class?"%(str(exc)))



class PassThrough(Exception):
    pass

class SkipAll(Exception):
    def __init__(self, retval):
        self.args = (retval, )
        self.retval = retval


class MappingFailedError(ValueError):
    def __init__(self, *args, **kwds):
        super(MappingFailedError, self).__init__(*args, **kwds)
        self.scopes = deque()

    def __str__(self):
        args = self.args
        if not isinstance(args, (list, tuple)):
            args = (args, )
        return "".join(args) + " [%s]"%self.scope_name
    
    def wrap_with_scope(self, scope):
        self.scopes.appendleft(scope)

    @property
    def scope_name(self):
        if not self.scopes:
            return u""
        acc = self.scopes[0]
        for idx in range(1, len(self.scopes)):
            scope = self.scopes[idx]
            if scope.startswith(u'[') or scope.startswith(u'('):
                acc += scope
            else:
                acc += "."
                acc += scope
        return acc


class LoadFailedError(MappingFailedError):
    pass

class DumpFailedError(MappingFailedError):
    pass


class MetaAttrObject(type):
    def __init__(cls, name, bases, members):
        type.__init__(cls, name, bases, members)

        cls._cached_attributes = None
        cls._cached_type_signature = None

        attrs = members.get('attributes', {})
        cls.raw_attributes = attrs
        assert type(attrs) == dict, repr(attrs)
        try:
            delattr(cls, 'attributes')
        except AttributeError:
            pass


class AttrObject(object):
    __metaclass__ = MetaAttrObject
    def __init__(self, *args, **kwds):
        if '__bootstrap__' not in kwds and '__raw__' not in kwds:
            self.do_schematic_construction(args, kwds)
        else:
            self.do_raw_construction(args, kwds)

        for postinit in self.class_attr_chain("__postinit__"):
            postinit(self)

    @classmethod
    def class_attr_chain(cls, attrname):
        already_visited_classes = set()

        def ascend(supcls):
            if supcls in already_visited_classes:
                return
            already_visited_classes.add(supcls)

            if type(supcls) != AttrObject:
                for base in supcls.__bases__:
                    if not issubclass(supcls, AttrObject):
                        continue
                    for supsup in ascend(base):
                        yield supsup

            if attrname in supcls.__dict__:
                yield supcls.__dict__[attrname]
        return ascend(cls)


    @classmethod
    def get_attr_adapter(cls):
        return AttrObjectAdapter(attrobj_cls=cls, __bootstrap__=True)

    def do_schematic_construction(self, args, kwds):
        adapter = self.get_attr_adapter()
        adapter.update_obj(self, args, kwds)

    def do_raw_construction(self, args, kwds):
        kwds.pop('__bootstrap__', None)
        kwds.pop('__raw__', None)
        
        for key in kwds:
            setattr(self, key, kwds[key])

    @classmethod
    def _extended_attributes(cls):
        attribs = {}
        for ra in cls.class_attr_chain("raw_attributes"):
            attribs.update(ra)
        return attribs

    @classmethod
    def unified_attributes(cls):
        if cls._cached_attributes is None:
            cls._cached_attributes = cls._extended_attributes()
        return cls._cached_attributes

    @classmethod
    def type_signature(cls):
        if cls._cached_type_signature is None:
            cls._cached_type_signature = AttributeSignature(Attr.coerce_dict(
                cls.unified_attributes()
            ))
        return cls._cached_type_signature

    def items(self):
        for key in AttributeSignature(self.unified_attributes()):
            yield key, getattr(self, key)

    def shallow_dict(self):
        return dict(self.items())

    @classmethod
    def extract_class(cls, loaded_dict):
        return cls

    @classmethod
    def inject_extra(cls, dumped_dict):
        pass

    @classmethod
    def build(cls, *args, **kwds):
        return cls(*args, **kwds)

    @classmethod
    def loads_dict(cls, dict_, env_type="object"):
        adapter = cls.get_attr_adapter()
        return adapter.loads(dict_, env_type)

    @classmethod
    def loads_json_dict(cls, json_dict):
        return cls.loads_dict(json_dict, env_type="json")

    @classmethod
    def loads_json(cls, s):
        json_dict = json.loads(s)
        return cls.loads_json_dict(json_dict)

    def dumps_dict(self, env_type="object"):
        adapter = self.get_attr_adapter()
        return adapter.dumps(self, env_type)

    def dumps_json_dict(self):
        return self.dumps_dict(env_type="json")

    def dumps_json(self):
        return json.dumps(self.dumps_json_dict())

    def to_dict(self):
        return self.dumps_dict()

    def to_json_dict(self):
        return self.dumps_json_dict()

    def _repr_indent(self, indent):
        IND = " "*indent
        IND_NEXT = " "*(indent + 4)

        acc = ["<", self.__class__.__name__]

        first = True
        items = list(self.items())
        if items:
            acc.append(" {\n")

        for k, v in items:
            acc.append(IND_NEXT)
            acc.append(k)
            acc.append(" = ")
            if isinstance(v, AttrObject):
                acc.append(v._repr_indent(indent + 4))
            else:
                acc.append(repr(v))
            acc.append("\n")

        if items:
            acc.append("}")

        acc.append(">")
        return "".join(acc)

    def __repr__(self):
        return self._repr_indent(0)

    def __eq__(self, other):
        if type(self) == type(other):
            return all(
                getattr(self, key) == getattr(other, key)
                for key in self.type_signature()
            )
        return False



class Attr(AttrObject):
    _fast_coerce_chain = {}
    _fast_value_coerce_chain = {}
    _coerce_chain = {}

    @classmethod
    def _set_coerce_rule(cls, fast, is_value, *args):
        def wrapper(chain):
            assert isCallable(chain)

            if fast:
                if not is_value:
                    chain_dict = cls._fast_coerce_chain
                else:
                    chain_dict = cls._fast_value_coerce_chain
            else:
                chain_dict = cls._coerce_chain

            for arg in args:
                if arg not in chain_dict:
                    chain_dict[arg] = []
                chain_dict[arg].append(chain)
            return chain
        return wrapper

    @classmethod
    def fast_coerce_rule(cls, *exact_types):
        return cls._set_coerce_rule(True, False, *exact_types)

    @classmethod
    def fast_value_coerce_rule(cls, *exact_values):
        return cls._set_coerce_rule(True, True, *exact_values)

    @classmethod
    def coerce_rule(cls, *base_types):
        return cls._set_coerce_rule(False, False, *base_types)

    @classmethod
    def coerce(cls, obj):
        if isinstance(obj, Attr):
            return obj

        type_of_obj = type(obj)
        try:
            hash(obj)
        except TypeError:
            pass
        else:
            for chain in cls._fast_value_coerce_chain.get(obj, ()):
                retval = chain(obj)
                if retval is not None:
                    return retval

        for chain in cls._fast_coerce_chain.get(type_of_obj, ()):
            retval = chain(obj)
            if retval is not None:
                return retval

        # slow loop
        for base_type, chains in cls._coerce_chain.items():
            if isinstance(obj, base_type):
                for chain in chains:
                    retval = chain(obj)
                    if retval is not None:
                        return retval
        
        # treat it as lambda function and evaluate it
        if inspect.isfunction(obj):
            # evaluate a lambda
            return cls.coerce(obj())

        raise TypeError("No type coersion rule for the value %s."
                        " Did you forget to have it inherit either AttrObject or Attr?"%repr(obj))
    @classmethod
    def coerce_dict(cls, dict_):
        return {key: cls.coerce(val) for key, val in dict_.items()}

    @classmethod
    def coerce_list(cls, list_):
        return [Attr.coerce(item) for item in list_]

    def loads(self, val, env_type):
        raise NotImplementedError

    def dumps(self, obj, env_type):
        return NotImplementedError

    def key_not_present(self, access_key, env_type):
        raise LoadFailedError("KeyError")


class AnyAttr(Attr):
    def loads(self, val, env_type):
        return val

    def dumps(self, obj, env_type):
        return obj


class AttrOfAttr(Attr):
    # Meta-level Attr
    def loads(self, val, env_type):
        return Attr.coerce(val)

    def dumps(self, val, env_type):
        return val


@Attr.fast_value_coerce_rule(Attr)
def meta_attr_coerce_chain(obj):
    return AttrOfAttr()

class AttrDecorator(Attr):
    def get_wrapped_attr(self, env_type):
        raise NotImplementedError

    def do_get_wrapped_attr(self, env_type):
        return Attr.coerce(self.get_wrapped_attr(env_type))

    def wrap_loads(self, val, env_type):
        raise PassThrough

    def wrap_dumps(self, obj, env_type):
        raise PassThrough

    def loads(self, val, env_type):
        try:
            self.pre_loads(val)
            impl = self.do_get_wrapped_attr(env_type)
            preloaded_val = impl.loads(val, env_type)
            try:
                return self.wrap_loads(preloaded_val, env_type)
            except PassThrough:
                return preloaded_val
        except SkipAll as exc:
            return exc.retval
        except MappingFailedError as exc:
            self.on_mapping_failure(exc)
            raise

    def dumps(self, obj, env_type):
        try:
            impl = self.do_get_wrapped_attr(env_type)
            try:
                dumped_obj = self.wrap_dumps(obj, env_type)
            except PassThrough:
                dumped_obj = obj
            dumpval = impl.dumps(dumped_obj, env_type)
            return dumpval
        except SkipAll as exc:
            return exc.retval
        except MappingFailedError as exc:
            self.on_mapping_failure(exc)
            raise

    def pre_loads(self, val):
        pass

    def on_mapping_failure(self, exc):
        pass


class AttrWrapper(AttrDecorator):
    attributes = {
        "wrapped_attr#0": Attr
    }

    def get_wrapped_attr(self, env_type):
        return self.wrapped_attr



class ListAttr(Attr):
    attributes = {
        "*attrs": (lambda: ListAttr(attrs=[Attr], __bootstrap__=True))
    }

    def __postinit__(self):
        self.attrs = Attr.coerce_list(self.attrs)

    def loads(self, val, env_type):
        if not isinstance(val, Iterable):
            raise LoadFailedError("Iterable expected, got %s"%repr(val))

        attr_cycle = cycle(self.attrs)
        result = []
        try:
            for idx, (attr, val_item) in enumerate(izip(attr_cycle, val)):
                result.append(attr.loads(val_item, env_type))
        except MappingFailedError as exc:
            exc.wrap_with_scope(u"[%d]"%idx)
            raise
        return result

    def dumps(self, obj, env_type):
        attr_cycle = cycle(self.attrs)
        result = []
        try:
            for idx, (attr, obj_item) in enumerate(izip(attr_cycle, obj)):
                result.append(attr.dumps(obj_item, env_type))
        except MappingFailedError as exc:
            exc.wrap_with_scope(u"[%d]"%idx)
            raise
        return result

@Attr.fast_coerce_rule(list)
def list_expr_coerce_chain(obj):
    return ListAttr(*obj)


class SimpleTypeAttr(Attr):
    attributes = {
        "*types": (lambda: ListAttr(
            attrs=[
                SimpleTypeAttr(
                    types=[type],
                    __bootstrap__=True
                )
            ],
            __bootstrap__=True
        ))
    }

    def __postinit__(self):
        self.types = tuple(self.types)

    def loads(self, val, env_type):
        if isinstance(val, self.types):
            return val

        raise LoadFailedError("Type Mismatch: "
                              "%s doesn't match with types (%s)"
                              %(repr(val), ", ".join(map(repr, self.types))))

    def dumps(self, obj, env_type):
        if isinstance(obj, self.types):
            return obj

        raise DumpFailedError("Type Mismatch: "
                              "Nothing matched wit htypes (%s)"
                              %", ".join(map(repr, self.types)))


class SignatureDictAttr(AttrDecorator):
    attributes = {
        "signature#0": SimpleTypeAttr(types=[AttributeSignature],
                                      __bootstrap__=True)
    }

    def get_wrapped_attr(self, env_type):
        return SimpleTypeAttr(types=[dict], __bootstrap__=True)

    def wrap_loads(self, dict_, env_type):
        result = {}
        for key, attr in self.signature.items():
            try:
                try:
                    val = dict_[key]
                except KeyError:
                    obj = attr.key_not_present(key, env_type)
                else:
                    obj = attr.loads(val, env_type)
            except MappingFailedError as exc:
                exc.wrap_with_scope(key)
                raise

            result[key] = obj
        return result

    def wrap_dumps(self, dict_, env_type):
        result = {}
        for key, attr in self.signature.items():
            obj = dict_[key]
            try:
                val = attr.dumps(obj, env_type)
            except MappingFailedError as exc:
                exc.wrap_with_scope(key)
                raise
            result[key] = val
        return result


class AttrObjectAdapter(Attr):
    attributes = {
        "attrobj_cls#0": SimpleTypeAttr(types=[MetaAttrObject],
                                        __bootstrap__=True)
    }


    def get_signature_dict_attr(self, attrobj_cls):
        assert isinstance(attrobj_cls, MetaAttrObject)

        return SignatureDictAttr(
            signature=attrobj_cls.type_signature(),
            __bootstrap__=True
        )

    def loads(self, val, env_type):
        if isinstance(val, AttrObject):
            if not isinstance(val, self.attrobj_cls):
                raise LoadFailedError('Attribute should be an instance of subclass of %s' % repr(self.attrobj_cls))
            return val

        elif isinstance(val, dict):
            clazz = self.attrobj_cls.extract_class(val)
            sig_attr = self.get_signature_dict_attr(clazz)
            loaded_dict = sig_attr.loads(val, env_type)
            loaded_dict["__raw__"] = True
            return clazz(**loaded_dict)
        else:
            raise LoadFailedError('Expected an AttrObject or a dict, got %s'%repr(val))

    def dumps(self, obj, env_type):
        sig_attr = self.get_signature_dict_attr(obj.__class__)
        dumped_dict = sig_attr.dumps(obj.shallow_dict(), env_type)
        obj.inject_extra(dumped_dict)
        return dumped_dict


    def update_obj(self, obj, args, kwds):
        sig_attr = self.get_signature_dict_attr(obj.__class__)
        applied_dict = obj.type_signature().apply_arguments(args, kwds)
        loaded_dict = sig_attr.loads(applied_dict, "object")
        for k, v in loaded_dict.items():
            setattr(obj, k, v)


@Attr.coerce_rule(type)
def adapt_attrobj_coerce_chain(obj):
    if issubclass(obj, AttrObject):
        return AttrObjectAdapter(obj)

class OptionalAttr(AttrWrapper):
    attributes = {
        "default": (lambda: OptionalAttr(wrapped_attr=AnyAttr(),
                                         default=None,
                                         __bootstrap__=True))
    }

    def wrap_dumps(self, obj, env_type):
        if obj is None:
            raise SkipAll(obj)
        return obj

    def key_not_present(self, access_key, env_type):
        if isCallable(self.default):
            return self.default() # factory가 들어온 경우
        else:
            return self.default



predefined_literal_types = (int, long, float, basestring,
                            str, unicode, bool, type(None))


class LiteralAttr(Attr):
    attributes = {
        "value#0": AnyAttr()
    }

    def loads(self, val, env_type):
        if val != self.value:
            raise LoadFailedError("Value mismatch: Expected %s, got %s"%(self.value, val))
        return val

    def dumps(self, obj, env_type):
        return obj



@Attr.fast_coerce_rule(*predefined_literal_types)
def literal_value_coerce_chain(obj):
    return LiteralAttr(obj)


@Attr.fast_value_coerce_rule(bool, type(None), dict)
def literal_type_coerce_chain(obj):
    return SimpleTypeAttr(obj)



class IntegerAttr(AttrDecorator):
    def get_wrapped_attr(self, env_type):
        return SimpleTypeAttr(int, long)


@Attr.fast_value_coerce_rule(int, long)
def integer_type_coerce_chain(obj):
    return IntegerAttr()


class FloatAttr(AttrDecorator):
    def get_wrapped_attr(self, env_type):
        return SimpleTypeAttr(int, long, float)

    def wrap_loads(self, val, env_type):
        return float(val)


@Attr.fast_value_coerce_rule(float)
def float_type_coerce_chain(obj):
    return FloatAttr()


class BytesAttr(AttrDecorator):
    attributes = {
        "encoding": (lambda: OptionalAttr(
            UnicodeAttr(encoding=u"utf-8", __bootstrap__=True),
            default=u"utf-8"
        ))
    }

    def get_wrapped_attr(self, env_type):
        return SimpleTypeAttr(bytes, unicode)

    def wrap_loads(self, obj, env_type):
        if isinstance(obj, unicode):
            try:
                obj = obj.encode(self.encoding)
            except UnicodeError as exc:
                raise LoadFailedError(str(exc))
        return obj

StrAttr = BytesAttr

class UnicodeAttr(AttrDecorator):
    attributes = {
        "encoding": (lambda: OptionalAttr(
            UnicodeAttr(encoding=u"utf-8", __bootstrap__=True),
            default=u"utf-8"
        ))
    }

    def get_wrapped_attr(self, env_type):
        return SimpleTypeAttr(bytes, unicode)

    def wrap_loads(self, obj, env_type):
        if isinstance(obj, bytes):
            try:
                obj = obj.decode(self.encoding)
            except UnicodeError as exc:
                raise LoadFailedError(str(exc))
        return obj




@Attr.fast_value_coerce_rule(bytes)
def bytes_type_coerce_chain(obj):
    return BytesAttr()


@Attr.fast_value_coerce_rule(basestring, unicode)
def unicode_type_coerce_chain(obj):
    return UnicodeAttr()


class NoneableAttr(AttrWrapper):
    def pre_loads(self, val):
        if val is None:
            raise SkipAll(val)

    def wrap_dumps(self, obj, env_type):
        if obj is None:
            raise SkipAll(val)
        return obj



class DatetimeAttr(Attr):
    attributes = {
        "format": OptionalAttr(unicode, default=u"%Y-%m-%d %H:%M:%S")
    }

    def loads(self, val, env_type):
        if isinstance(val, basestring):
            try:
                return datetime.strptime(val, self.format)
            except ValueError as exc:
                raise LoadFailedError(str(exc))
        elif isinstance(val, datetime):
            return val
        else:
            raise LoadFailedError()

    def dumps(self, obj, env_type):
        if env_type == "json":
            return obj.strftime(self.format)
        else:
            return obj





sre_pattern_type = type(re.compile(u""))
class RegexAttr(Attr):
    attributes = {
        "regex#0": basestring,
        "compiled_regex": OptionalAttr(SimpleTypeAttr(sre_pattern_type))
    }

    def __postinit__(self):
        if self.compiled_regex is not None:
            self.compiled_regex = re.compile(self.regex)

    def loads(self, val, env_type):
        mat = self.compiled_regex.match(val)
        if mat is None:
            raise LoadFailedError("Regex Mismatch: re.match(%s, %s) is None )"%(repr(self.regex), repr(val)))
        return mat

    def dumps(self, obj, env_type):
        return obj.group(0)

@Attr.fast_coerce_rule(sre_pattern_type)
def re_type_coerce_chain(obj):
    return RegexAttr(u"", compiled_regex=obj)


class ChoiceAttr(AttrDecorator):
    attributes = {
        "choices#0": [SimpleTypeAttr(*predefined_literal_types)]
    }
    
    def get_wrapped_attr(self, env_type):
        return AnyAttr()

    def wrap_loads(self, val, env_type):
        if val not in self.choices:
            raise LoadFailedError("%s doesn't matched with choices: %s"%(repr(val), ", ".join(map(repr, self.choices))))
        raise PassThrough


class StringChoiceAttr(ChoiceAttr):
    attributes = {
        "choices#0": [basestring]
    }


class DictAttr(AttrDecorator):
    attributes = {
        "arg#0": dict
    }

    def __postinit__(self):
        self._signature = AttributeSignature(Attr.coerce_dict(self.arg))

    def get_wrapped_attr(self, env_type):
        return SignatureDictAttr(self._signature)

@Attr.fast_coerce_rule(dict)
def dict_type_coerce_chain(obj):
    return DictAttr(obj)

class ConstantAttr(Attr):
    attributes = {
        "value#0": AnyAttr()
    }

    def loads(self, val, env_type):
        return self.value

    def dumps(self, obj, env_type):
        return obj

    def key_not_present(self, access_key, env_type):
        return self.value


class AbstractAttrObject(AttrObject):
    type_key = "_type"
    type_value = None

    @classmethod
    def _get_type_value(cls):
        if cls.type_value is None:
            return cls.__name__
        else:
            return cls.type_value

    @classmethod
    def extract_class(cls, loaded_dict):
        try:
            type_value = loaded_dict.pop(cls.type_key)
            for subcls in _all_subclasses(cls):
                if subcls._get_type_value() == type_value:
                    return subcls
            raise KeyError
        except KeyError:
            raise LoadFailedError('Failed to guess a concrete class from the type key %s; got %s'%(repr(cls.type_key), loaded_dict))

    @classmethod
    def inject_extra(cls, dumped_dict):
        dumped_dict[cls.type_key] = cls._get_type_value()

