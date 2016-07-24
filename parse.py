# coding: utf-8


def parse_pattern(s):
    try:
        if s.startswith(u"**"):
            return u"varkwd", None, s[2:]
        elif s.startswith(u"*"):
            return u"vararg", None, s[1:]
        elif u"#" in s:
            idx = s.rindex("#")
            tag_str = s[idx + 1:]
            name = s[:idx]
            tag = int(tag_str)

            if idx < 0:
                raise ValueError

            return u"argument", tag, name
        else:
            return u"keyword", None, s
    except ValueError:
        raise ValueError("Invalid attribute name pattern: %s"%s)

ordinal = lambda n: "%d%s" % (n,"tsnrhtdd"[(n/10%10!=1)*(n%10<4)*n%10::4])
class AttributeSignature(dict):
    def __init__(self, signature):
        super(dict, self).__init__()

        self._args = []
        self._maxarg = 0
        self._kwds = []
        self._varkwd = None
        self._vararg = None

        for key, value in signature.items():
            category, index, attrname = parse_pattern(key)
            if category == u'varkwd':
                self._varkwd = attrname
            elif category == u'vararg':
                self._vararg = attrname
            elif category == u'argument':
                if self._maxarg < index:
                    self._maxarg = index

                self._args.extend([None] * max(0, index - len(self._args) + 1))
                self._args[index] = attrname
            else:
                self._kwds.append(attrname)
            self[attrname] = value
    

        for idx, arg_attrname in enumerate(self._args):
            if arg_attrname is None:
                raise TypeError(
                    "<argname>#" +str(idx) + " required."
                    " (the %s positional argument out of %s)"%(
                        ordinal(idx + 1),
                        self._maxarg
                    )
                )

    def has_var_kwds(self):
        return self._varkwd is not None
        
    def apply_arguments(self, args, kwargs):
        result = {}

        params = self._args
        maxarg = self._args
        param_idx = 0
        arg_idx = 0

        if self._vararg:
            result[self._vararg] = []

        if self._varkwd:
            result[self._varkwd] = {}

        while param_idx < len(params) and arg_idx < len(args):
            attrname = params[param_idx]
            attrvalue = args[arg_idx]
            result[attrname] = attrvalue
            param_idx += 1
            arg_idx += 1


        poskeyword = [] # positional parameters applied by keyword ones

        if param_idx < len(params): # positional parameters are not exhausted
            for idx in range(param_idx, len(params)):
                param = params[idx]
                try:
                    attrvalue = kwargs[param]
                    result[param] = attrvalue
                    poskeyword.append(param)
                except KeyError:
                    raise TypeError("The %s positional argument '%s' is not applied"%(ordinal(idx + 1), param))

        elif arg_idx < len(args): # when non-keyword arguments still not exhausted
            if self._vararg:
                result[self._vararg] = args[arg_idx:]
            else:
                raise TypeError('Unexpected %s positional argument'%ordinal(arg_idx + 1))
    
        
        for keyparam in self._kwds:
            if keyparam in poskeyword:
                continue
            try:
                result[keyparam] = kwargs[keyparam]
            except KeyError:
                # raise TypeError('No value assigned to keyword argument "%s"'%keyparam)
                pass
    
        redundant_keywords = [applied_keyword
                              for applied_keyword in kwargs
                              if applied_keyword not in result]

        if redundant_keywords:
            if self._varkwd:
                result[self._varkwd] = {key: kwargs[key] for key in redundant_keywords}
            else:
                raise TypeError(
                    "Unexpected keyword arguments: %s"
                    %(", ".join(map(repr, redundant_keywords)))
                )

        return result


if __name__ == '__main__':
    print parse_pattern("keyword")
    print parse_pattern("attrname#2")
    print parse_pattern("attrname#4")
    print parse_pattern("*args")
    print parse_pattern("**kwds")

    
    signature = AttributeSignature({
        "a#0": 0,
        "b#1": 0,
        "c": 0,
        "d": 0
    })

    # print signature.apply_arguments([1], {"c": 1, "d": 1})
    # print signature.apply_arguments([1, 1], {'b': 1, "c": 1, "d": 1})
    # print signature.apply_arguments([1, 1], {'b': 1, "d": 1})
    # print signature.apply_arguments([1, 1], {"c": 1, "d": 1, "f": 1})
    
    signature_var = AttributeSignature({
        "a#0": 0,
        "b#1": 0,
        "c": 0,
        "d": 0,
        "*list": 0,
        "**dict": 0,
    })
    print signature_var.apply_arguments([1, 1, 'z', 't'], {"c": 1, "d": 1, "f": 1})

