import abc
import enum
import sys
import os


# interpreter

class TinyLangInterpreter:
    """ An interpreter that interprets and executes tiny-lang code.
    
    Once initialized, the interpreter holds all parsed code, goto labels and context.
    
    Attributes:
        statements: A list that holds all parsed code.
            Its indices matches the line number.
        labels: A dict that holds all goto labels.
            The keys are label names, values are line numbers.
        context: A dict that holds all runtime variables.
            The keys are variable names, values are variable values.
    """
    
    def __init__(self):
        """ Create and initialize a tiny-lang interpreter. """
        self.statements = []
        self.labels = {}
        self.context = {}
    
    def input(self):
        """ The input function.
        
        This function is used when executing an input statement.
        
        Returns:
            The input from stdin (not checked format, not converted)
        """
        return input()
    
    def print(self, obj):
        """ The print function.
        
        It is used when executing a print statement.
        This function dose not add line separator as suffix.
        
        Args:
            obj: Something to print. It can be anything that printable in Python.
        """
        print(obj, end='')
    
    @staticmethod
    def parse_one_line_string(line, string):
        """ Parse an one-line string into label and statement.
        
        Args:
            line: The line number of this string, used for error locating.
            string: An one-line string (without any line separator)
        
        Returns:
            Label and statement, both witch can be None
        """
        string = string.strip()
        label, statement = quoted_split_first(string, ':')
        if label is not None:
            label = label.strip()
            if len(label) > 0:
                label = check_name_legal(line, label)
            else:
                label = None
        
        statement = statement.strip()
        if len(statement) == 0:
            statement = None
        else:
            statement = Statement.parse(line, statement)
        
        return label, statement
    
    def load_string(self, string, keep_empty=True):
        """ Load a string as tiny-lang code
        
        Parse the string (can be multi-line) as tiny-lang code, get statements and goto labels.
        Then the interpreter stores the parsed statements and goto labels for further execution.
        (this function does not perform any execution)
        
        Args:
            string: A string of tiny-lang code (can be multi-line)
            keep_empty: Whether to count the line number when meeting a empty lines.
                Use True to run a script file in order to match line numbers.
                Use False in interactive mode to ignore empty lines.
        
        Returns:
            The first line number of the loaded string. From this line we can execute the code.
            It can be not 0 in interactive mode.
        """
        from_line = len(self.statements)
        for one_line_string in string.splitlines():
            line = len(self.statements)
            
            try:
                label, statement = self.parse_one_line_string(line, one_line_string)
            except TinyLangCompileError:
                raise
            except RuntimeError as e:
                raise UnknownCompileError(line, e)
            
            if not keep_empty and label is None and statement is None:
                continue
            self.statements.append(statement)
            if label is not None:
                label = check_name_legal(line, label)
                self.labels[label] = line
        
        return from_line
    
    def execute_from(self, line):
        """ Execute code starting from a specified line.
        
        The interpreter will automatically run the next line unless it meets a goto instruction.
        The interpreter stops when meets the end of code or occurs any runtime error.
        
        Args:
            line: The line number from which to run the code.
        
        Returns:
            The number of next line. It should be bigger then the last line number.
        """
        while 0 <= line < len(self.statements):
            statement = self.statements[line]
            if statement is not None:
                goto_label = statement.exec(line, self)
            else:
                goto_label = None
            
            if goto_label is not None:
                next_line = self.labels.get(goto_label)
                if next_line is None:
                    raise IllegalGotoLabelError(line, goto_label)
            else:
                next_line = line + 1
            
            line = next_line
        return line
    
    def execute_string(self, string, keep_empty=True):
        """ Parse a string (can be multi-line) as and then execute it.
        
        Args:
            string: A string of tiny-lang code (can be multi-line)
            keep_empty: whether to count the line number when meeting a empty lines.
                Use True to run a script file in order to match line numbers.
                Use False in interactive mode to ignore empty lines.
        
        Returns:
            The number of next line. It should be bigger then the last line number.
        """
        from_line = self.load_string(string, keep_empty)
        next_line = self.execute_from(from_line)
        return next_line


# statement

class Statement(abc.ABC):
    
    @staticmethod
    def parse(line, string):
        keyword, content = quoted_split_first(string, ' ')
        if keyword is None:
            keyword = string
            content = ""
        cls = {
            'let': LetStatement,
            'if': IfStatement,
            'input': InputStatement,
            'print': PrintStatement,
        }.get(keyword)
        if cls is None:
            raise TinyLangSyntaxError(line, '"' + keyword + '" is not a legal keyword!')
        return cls.parse(line, content)
    
    @abc.abstractmethod
    def exec(self, line, interpreter):
        pass


class LetStatement(Statement):
    def __init__(self, name, expr):
        self.name = name
        self.expr = expr
    
    @staticmethod
    def parse(line, string):
        name, expresion = quoted_split_first(string, '=')
        
        if name is None:
            raise TinyLangSyntaxError(line, 'an assignment operator "=" is expected!')
        name = name.strip()
        if len(name) == 0:
            raise TinyLangSyntaxError(line, 'a variable name is expected for assignment!')
        name = check_name_legal(line, name)
        
        expresion = expresion.strip()
        if len(expresion) == 0:
            raise TinyLangSyntaxError(line, 'an expresion or value is expected for assignment!')
        expresion = Expresion.parse(line, expresion)
        
        return LetStatement(name, expresion)
    
    def exec(self, line, interpreter):
        interpreter.context[self.name] = self.expr.eval(line, interpreter.context)
        return None


class IfStatement(Statement):
    def __init__(self, expr, target):
        self.target = target
        self.expr = expr
    
    @staticmethod
    def parse(line, string):
        expresion, target = quoted_split_first(string, 'goto')
        
        if expresion is None:
            raise TinyLangSyntaxError(line, 'a word "goto" is expected!')
        expresion = expresion.strip()
        expresion = Expresion.parse(line, expresion)
        
        target = target.strip()
        if len(target) == 0:
            raise TinyLangSyntaxError(line, 'a target label name is expected!')
        
        return IfStatement(expresion, target)
    
    def exec(self, line, interpreter):
        if self.expr.eval(line, interpreter.context) == 0:
            return None
        else:
            return self.target


class InputStatement(Statement):
    def __init__(self, name):
        self.name = name
    
    @staticmethod
    def parse(line, string):
        name = string
        name = name.strip()
        if len(name) == 0:
            raise TinyLangSyntaxError(line, 'a variable name (to store the input value) is expected!')
        name = check_name_legal(line, name)
        return InputStatement(name)
    
    def exec(self, line, interpreter):
        value = interpreter.input()
        try:
            value = float(value)
        except ValueError:
            raise IllegalInputError(line)
        interpreter.context[self.name] = value
        return None


class PrintStatement(Statement):
    def __init__(self, *expr_list):
        self.expr_list = expr_list
    
    @staticmethod
    def parse(line, string):
        string = string.strip()
        if len(string) == 0:
            return PrintStatement()
        
        segments, closed = quoted_split(string, ',', '"')
        if not closed:
            raise TinyLangSyntaxError(line, "quote not closed!")
        
        expr_list = []
        for segment in segments:
            segment = segment.strip()
            if len(segment) == 0:
                raise TinyLangSyntaxError(line, 'an expresion or value is expected')
            expr_list.append(Expresion.parse(line, segment))
        
        return PrintStatement(*expr_list)
    
    def exec(self, line, interpreter):
        if len(self.expr_list) > 0:
            interpreter.print(self.expr_list[0].eval(line, interpreter.context))
            for expr in self.expr_list[1:]:
                interpreter.print(' ')
                interpreter.print(expr.eval(line, interpreter.context))
        interpreter.print('\n')
        return None


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
        raise TinyLangSyntaxError(line, "Can not parse the string as neither a float number nor a string!")
    
    def eval(self, line, context):
        return self.value


class ReferenceExpresion(Expresion):
    def __init__(self, name):
        self.name = name
    
    @staticmethod
    def parse(line, string: str):
        name = string.strip()
        name = check_name_legal(line, name)
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
        _, func = self.operator.value
        x = self.expr1.eval(line, context)
        y = self.expr2.eval(line, context)
        return func(x, y)


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
        message += " (at line " + str(line) + ")"
        super().__init__(message)
        self.line = line


class TinyLangSyntaxError(TinyLangCompileError):
    def __init__(self, line, message):
        message = "Syntax error:" + message
        super().__init__(line, message)


class UnknownCompileError(TinyLangCompileError):
    def __init__(self, line, error):
        self.error = error
        message = "Syntax error: compile failed due to the following exception."
        super().__init__(line, message)
    
    def __str__(self) -> str:
        return super().__str__() + "\n" + str(self.error)


# utils

def quoted_split_first(string, sep=',', quote='"'):
    cursor = 0
    while True:
        quote_pos = string.find(quote, cursor)
        sep_pos = string.find(sep, cursor)
        if sep_pos == -1:
            break
        if quote_pos == -1:
            break
        if sep_pos < quote_pos:
            break
        right_quote_pos = string.find(quote, quote_pos + 1)
        if right_quote_pos == -1:
            sep_pos = -1
            break
        cursor = right_quote_pos + 1
    
    if sep_pos != -1:
        return string[:sep_pos], string[sep_pos + len(sep):]
    else:
        return None, string


def quoted_split(string, sep=',', quote='"'):
    quote_segments = string.split(quote)
    
    quoted = False
    segments = quote_segments[0].split(sep)
    
    for i, quote_segment in enumerate(quote_segments[1:]):
        quoted = i % 2 == 0
        if quoted:
            segments[-1] += quote + quote_segment
        else:
            sep_segments = quote_segment.split(sep)
            segments[-1] += quote + sep_segments[0]
            segments.extend(sep_segments[1:])
    closed = not quoted
    return segments, closed


def check_name_legal(line, name):
    name = name.strip()
    
    if len(name) == 0:
        raise TinyLangSyntaxError(line, "name of variables and labels must not be empty!")
    
    message = '"' + name + '" is not a legal name of variable (label), it must not contains '
    if ' ' in name or '\t' in name:
        raise TinyLangSyntaxError(line, message + "spaces or tabs!")
    if ',' in name or ':' in name or '"' in name:
        raise TinyLangSyntaxError(line, message + "commas, colons or quotes!")
    if any(s in name for s in [op.value[0] for op in OperatorExpresion.Operator] + ["="]):
        raise TinyLangSyntaxError(line, message + "operators!")
    
    return name


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
    interpreter = TinyLangInterpreter()
    
    next_line = 0
    break_error = False
    while True:
        try:
            string = input('Line[' + str(next_line) + '] > ')
            next_line = interpreter.execute_string(string, keep_empty=False)
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
    interpreter = TinyLangInterpreter()
    with open(script_fn, 'r') as script_file:
        string = script_file.read()
    interpreter.execute_string(string, keep_empty=True)


if __name__ == '__main__':
    main()
