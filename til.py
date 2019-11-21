import abc
import enum
import sys
import os


# runtime

class TinyLangRuntime:
    def __init__(self):
        self.statements = []
        self.labels = {}
        self.context = {}
        self.next_line = None
    
    def input(self):
        return input()
    
    def print(self, obj):
        print(obj)
    
    @staticmethod
    def parse_one_line_string(line, string):
        string = string.strip()
        label, statement = split_next_word(string, ':')
        if label is not None:
            label = label.strip()
            if len(label) == 0:
                label = None
        
        statement = statement.strip()
        if len(statement) == 0:
            statement = None
        else:
            statement = Statement.parse(line, statement)
        
        return label, statement
    
    def load_string(self, string, keep_empty=True):
        from_line = len(self.statements)
        for one_line_string in string.splitlines():
            line = len(self.statements)
            label, statement = self.parse_one_line_string(line, one_line_string)
            if not keep_empty and label is None and statement is None:
                continue
            self.statements.append(statement)
            if label is not None:
                self.labels[label] = line
        return from_line
    
    def execute_from(self, line):
        self.next_line = line
        while 0 <= self.next_line < len(self.statements):
            statement = self.statements[self.next_line]
            if statement is not None:
                statement.exec(self)
        next_line = self.next_line
        self.next_line = None
        return next_line
    
    def execute_string(self, string, keep_empty=True):
        from_line = self.load_string(string, keep_empty)
        next_line = self.execute_from(from_line)
        return next_line


# expresion

class Expresion(abc.ABC):
    
    @staticmethod
    def parse(line, string: str):
        for cls in [ValueExpresion, OperatorExpresion, ReferenceExpresion]:
            try:
                return cls.parse(line, string)
            except TinyLangSyntaxError:
                pass
        raise TinyLangSyntaxError(line, 'Can not parse "' + string + '" as an expresion!')
    
    @abc.abstractmethod
    def eval(self, line, context):
        pass


class ValueExpresion(Expresion):
    def __init__(self, value):
        self.value = value
    
    @staticmethod
    def parse(line, string: str):
        string = string.strip()
        if string.startswith('"') and string.endswith('"'):
            value = string.strip('"')
            return ValueExpresion(value)
        if string.replace('.', '', 1).isdigit():
            value = float(string)
            return ValueExpresion(value)
        raise TinyLangSyntaxError(line, "Can not parse the string as neither a float number nor a string")
    
    def eval(self, line, context):
        return self.value


class ReferenceExpresion(Expresion):
    def __init__(self, name):
        self.name = name
    
    @staticmethod
    def parse(line, string: str):
        name = string.strip()
        name_legal(line, name)
        return ReferenceExpresion(name)
    
    def eval(self, line, context):
        value = context.get(self.name)
        if value is None:
            raise UndefinedVariableError(line, self.name)
        return value


class OperatorExpresion(Expresion):
    class Operator(enum.Enum):
        PL = '+', lambda x, y: x + y
        MI = '-', lambda x, y: x - y
        MU = '*', lambda x, y: x * y
        DI = '/', lambda x, y: x / y
        LT = '<', lambda x, y: float(x < y)
        LE = '<=', lambda x, y: float(x <= y)
        GT = '>', lambda x, y: float(x > y)
        GE = '>=', lambda x, y: float(x >= y)
        EQ = '==', lambda x, y: float(x == y)
        NE = '!=', lambda x, y: float(x != y)
    
    def __init__(self, operator, expr1, expr2):
        self.operator = operator
        self.expr1 = expr1
        self.expr2 = expr2
    
    @staticmethod
    def parse(line, string: str):
        operator = None
        operator_pos = -1
        for op in OperatorExpresion.Operator:
            s, _ = op.value
            operator_pos = string.find(s)
            if operator_pos != -1:
                operator = op
                break
        if operator_pos == -1 or operator is None:
            raise TinyLangSyntaxError(line, "Not found any operator in the expresion!")
        
        op_str, _ = operator.value
        expr1 = string[:operator_pos]
        expr1 = Expresion.parse(line, expr1)
        expr2 = string[operator_pos + len(op_str):]
        expr2 = Expresion.parse(line, expr2)
        return OperatorExpresion(operator, expr1, expr2)
    
    def eval(self, line, context):
        _, func = self.operator
        x = self.expr1.eval(context)
        y = self.expr2.eval(context)
        return func(x, y)


# statement

class Statement(abc.ABC):
    def __init__(self, line):
        self.line = line
    
    @staticmethod
    def parse(line, string):
        keyword, string = split_next_word(string, ' ')
        cls = {
            'let': LetStatement,
            'if': IfStatement,
            'input': InputStatement,
            'print': PrintStatement,
        }.get(keyword)
        if cls is None:
            raise TinyLangSyntaxError(line, 'can not recognize keyword "' + keyword + '"!')
        return cls.parse(line, string)
    
    @abc.abstractmethod
    def exec(self, runtime):
        pass


class LetStatement(Statement):
    def __init__(self, line, name, expr):
        super().__init__(line)
        self.name = name
        self.expr = expr
    
    @staticmethod
    def parse(line, string):
        name, expresion = split_next_word(string, '=')
        name = name.strip()
        name_legal(line, name)
        expresion = Expresion.parse(line, expresion)
        return LetStatement(line, name, expresion)
    
    def exec(self, runtime):
        runtime.context[self.name] = self.expr.eval(self.line, runtime.context)


class IfStatement(Statement):
    def __init__(self, line, expr, target):
        super().__init__(line)
        self.target = target
        self.expr = expr
    
    @staticmethod
    def parse(line, string):
        expresion, target = split_next_word(string, 'goto')
        expresion = expresion.strip()
        expresion = Expresion.parse(line, expresion)
        target = target.strip()
        return IfStatement(line, expresion, target)
    
    def exec(self, runtime):
        if self.expr.eval() == 0:
            return
        target_line = runtime.labels.get(self.target)
        if target_line is None:
            raise IllegalGotoLabelError(self.line, self.target)
        runtime.next_line = target_line


class InputStatement(Statement):
    def __init__(self, line, name):
        super().__init__(line)
        self.name = name
    
    @staticmethod
    def parse(line, string):
        name = string
        name = name.strip()
        name_legal(line, name)
        return InputStatement(line, name)
    
    def exec(self, runtime):
        value = runtime.input()
        try:
            value = float(value)
        except ValueError:
            raise IllegalInputError(self.line)
        runtime.context[self.name] = value


class PrintStatement(Statement):
    def __init__(self, line, *expr_list):
        super().__init__(line)
        self.expr_list = expr_list
    
    @staticmethod
    def parse(line, string):
        segments, closed = split_quoted(string, ',', '"')
        if not closed:
            raise TinyLangSyntaxError(line, "quote not closed!")
        expr_list = [Expresion.parse(line, segment) for segment in segments]
        return PrintStatement(line, *expr_list)
    
    def exec(self, runtime):
        for expr in self.expr_list:
            runtime.print(expr.eval(self.line, runtime.context))


# utils

def split_next_word(string, sep, start=0):
    cursor = string.find(sep, start)
    if cursor != -1:
        word = string[:cursor]
        return word, string[cursor + len(sep):]
    else:
        return None, string


def split_quoted(string, sep, quote):
    quote_split = string.split(quote)
    
    quoted = False
    first_piece = quote_split[0]
    segments = first_piece.split(sep)
    
    for i, qs in enumerate(quote_split[1:]):
        quoted = i % 2 == 0
        if quoted:
            segments[-1] += quote + qs
        else:
            sep_split = qs.split(sep)
            segments[-1] += quote + sep_split[0]
            segments.extend(sep_split[1:])
    closed = not quoted
    return segments, closed


def name_legal(line, name, throw=True):
    try:
        message = "name of variables and labels must not contains "
        if ' ' in name or '\t' in name:
            raise TinyLangSyntaxError(line, message + "spaces or tabs!")
        if ',' in name or ':' in name or '"' in name:
            raise TinyLangSyntaxError(line, message + "commas, colons or quotes!")
        if any(s in name for s, _ in (op.value for op in OperatorExpresion.Operator)):
            raise TinyLangSyntaxError(line, message + "operators!")
        return True
    except TinyLangSyntaxError:
        if throw:
            raise
        return False


# runtime error

class TinyLangRuntimeError(RuntimeError):
    def __init__(self, line, message):
        message += " (at line " + str(line) + ")"
        super().__init__(message)
        self.line = line


class UndefinedVariableError(TinyLangRuntimeError):
    def __init__(self, line, name):
        self.name = name
        message = "Undefined variable " + name + "!"
        super().__init__(line, message)


class IllegalGotoLabelError(TinyLangRuntimeError):
    def __init__(self, line, label):
        self.label = label
        message = "Illegal goto label " + label + "!"
        super().__init__(line, message)


class IllegalInputError(TinyLangRuntimeError):
    def __init__(self, line):
        message = "Illegal or missing input!"
        super().__init__(line, message)


# compile error

class TinyLangCompileError(RuntimeError):
    def __init__(self, line, message):
        message += " at line " + str(line) + "!"
        super().__init__(message)
        self.line = line


class TinyLangSyntaxError(TinyLangCompileError):
    def __init__(self, line, message):
        message = "Syntax error:" + message + " at line " + str(line) + "!"
        super().__init__(line, message)


# main


def main():
    args = sys.argv
    work_dir = args[0]
    os.chdir(os.path.dirname(work_dir))
    if len(args) == 1:
        main_interactive()
    elif len(args) == 2:
        script_fn = args[1]
        main_script_file(script_fn)
    else:
        raise RuntimeError("Expected 1 parameter or no parameters, given " + str(len(args) - 1) + ".")


def main_interactive():
    runtime = TinyLangRuntime()
    
    next_line = 0
    break_error = False
    while True:
        try:
            string = input('Line[' + str(next_line) + '] > ')
            next_line = runtime.execute_string(string, keep_empty=False)
            if next_line < 0:
                break
        except TinyLangCompileError as e:
            print(e)
            continue
        except TinyLangRuntimeError as e:
            break_error = e
            break
        except EOFError:
            break
    
    if break_error:
        print()
        print("terminated with error")
        print(break_error)
    else:
        print()
        print("finished")


def main_script_file(script_fn):
    runtime = TinyLangRuntime()
    with open(script_fn, 'r') as script_file:
        string = script_file.read()
    runtime.execute_string(string, keep_empty=True)


if __name__ == '__main__':
    main()
