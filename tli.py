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
            The list items can be None if there is no statement on this line.
            It is not allowed to have more than one statement at a single line.
        next_line: The number of line where the execution was paused.
            When the interpreter is resumed, by default it will execute the code from this line.
        labels: A dict that holds all goto labels.
            The keys are label names, values are line numbers.
        context: A dict that holds all runtime variables.
            The keys are variable names, values are variable values.
    """
    
    def __init__(self):
        """ Create and initialize a tiny-lang interpreter. """
        self.statements = []
        self.next_line = 0
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
    
    def resume(self, from_line=None):
        """ Resume the execution of code
        
        The followings are the rules of flow control:
         - By default the code is sequentially executed line by line.
         - When executing the goto instruction, the execution flow can be redirected to some other line.
         - When meeting some unreachable line (for example, the end of code), the interpreter pauses the execution.
         - When occurs runtime error, the interpreter pauses the execution.
        
        Args:
            from_line: the line number from which the execution goes.
                If given None, it will takes the value of attribute `next_line`.
        
        Returns:
            The the line number where the execution was paused.
        """
        
        # determine the next_line
        if from_line is not None:
            self.next_line = from_line
        
        # execute the statements line by line
        while 0 <= self.next_line < len(self.statements):
            this_line = self.next_line
            self.next_line = this_line + 1
            statement = self.statements[this_line]
            if statement is not None:
                statement.exec(this_line, self)
        
        # return the line number where the execution was paused.
        return self.next_line
    
    @staticmethod
    def parse_one_line_string(line, string):
        """ Parse an one-line string into label and statement.
        
        Args:
            line: The line number of this string, used for error locating.
            string: An one-line string (without any line separator)
        
        Returns:
            Label and statement, both witch can be None
        """
        
        # split out the label name (if exists)
        label, statement = quoted_split_first(string, ':')
        if label is not None:
            label = check_name_legal(line, label)
        
        # parse the statement (if exists)
        statement = statement.strip()
        if len(statement) > 0:
            statement = Statement.parse(line, statement)
        else:
            statement = None
        
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
        """
        for one_line_string in string.splitlines():
            line = len(self.statements)
            
            # parse the one-line string
            try:
                label, statement = self.parse_one_line_string(line, one_line_string)
            except TinyLangCompileError:
                raise
            except RuntimeError as e:
                # catch any unrecognized error in compile time
                # raise it as an UnknownCompileError
                raise UnknownCompileError(line, e)
            
            # check if the line is empty
            if not keep_empty and label is None and statement is None:
                continue
            
            # store the parsed statement and label
            # (in order to match the line number, the statement can be None)
            self.statements.append(statement)
            if label is not None:
                self.labels[label] = line
    
    def execute_string(self, string, keep_empty=True):
        """ Parse a string (can be multi-line) as and then execute it.
        
        Args:
            string: A string of tiny-lang code (can be multi-line)
            keep_empty: whether to count the line number when meeting a empty lines.
                Use True to run a script file in order to match line numbers.
                Use False in interactive mode to ignore empty lines.
        
        Returns:
            The the line number where the execution was paused.
        """
        self.load_string(string, keep_empty)
        return self.resume()


# statement

class Statement(abc.ABC):
    """ A basic component of tiny-lang code.
    
    The execution of a statement is closely related with the interpreter.
    
    There 4 types of statement
     - let-statement: modify the context
     - if-statement: change the next line of execution
     - input-statement: receive something from the outside
     - print-statement: send something to the outside
    
    """
    
    @staticmethod
    def parse(line, string):
        """ Parse a string into a tiny-lang statement.
        
        This function can detect the type of statement and parse it in a right way.
        
        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string without any label. 
                It should start with one of the keywords: let, if, input, print.
        
        Returns:
            A parsed typed statement.
        """
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
        """ Execute the statement.
        
        This is an abstract method. It should be implemented in subclasses.
        
        Args:
            line: The line number of this string, used for error locating.
            interpreter: The interpreter, on which the statement is executed.
        
        """
        pass


class LetStatement(Statement):
    """ A statement that performs variable assignment. """
    
    def __init__(self, name, value_expr):
        """
        Args:
            name: The name of a variable, to which the value will be assigned.
            value_expr: An expression, the value of which will be assigned to the variable.
        """
        self.name = name
        self.value_expr = value_expr
    
    @staticmethod
    def parse(line, string):
        """ Parse a string into a let-statement
        
        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string without labels or keywords.
        
        Returns:
            A parsed let-statement.
        """
        name, expression = quoted_split_first(string, '=')
        
        if name is None:
            raise TinyLangSyntaxError(line, 'an assignment operator "=" is expected!')
        name = name.strip()
        if len(name) == 0:
            raise TinyLangSyntaxError(line, 'a variable name is expected for assignment!')
        name = check_name_legal(line, name)
        
        expression = expression.strip()
        if len(expression) == 0:
            raise TinyLangSyntaxError(line, 'an expression or value is expected for assignment!')
        expression = Expression.parse(line, expression)
        
        return LetStatement(name, expression)
    
    def exec(self, line, interpreter):
        """ Execute the assignment
        
        Args:
            line: The line number of this string, used for error locating.
            interpreter: The interpreter, the context of which will be changed.
        """
        value = self.value_expr.eval(line, interpreter.context)
        interpreter.context[self.name] = value


class IfStatement(Statement):
    """ A statement that redirects the execution flow under a certain condition. """
    
    def __init__(self, cond_expr, target):
        """
        Args:
            cond_expr: An expression, the result of which determines whether to redirect the execution flow.
            target: A name of label, to which the execution flow will be redirected.
        """
        self.target = target
        self.cond_expr = cond_expr
    
    @staticmethod
    def parse(line, string):
        """ Parse a string into an if-statement
        
        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string without labels or keywords.
        
        Returns:
            A parsed if-statement.
        """
        expression, target = quoted_split_first(string, 'goto')
        
        if expression is None:
            raise TinyLangSyntaxError(line, 'a word "goto" is expected!')
        expression = expression.strip()
        expression = Expression.parse(line, expression)
        
        target = target.strip()
        if len(target) == 0:
            raise TinyLangSyntaxError(line, 'a target label name is expected!')
        
        return IfStatement(expression, target)
    
    def exec(self, line, interpreter):
        """ Evaluate the condition expression and perform the redirection if the result is true.
        
        Args:
            line: The line number of this string, used for error locating.
            interpreter: The interpreter, the attribute `next_line` of which will be changed the condition is true.
        """
        if self.cond_expr.eval(line, interpreter.context) != 0:
            target_line = interpreter.labels.get(self.target)
            if target_line is None:
                raise IllegalGotoLabelError(line, self.target)
            interpreter.next_line = target_line


class InputStatement(Statement):
    """ A statement that receives an input from the outside though the interpreter. """
    
    def __init__(self, name):
        """
        Args:
            name: A name of variable, to which the input will be stored.
        """
        self.name = name
    
    @staticmethod
    def parse(line, string):
        """ Parse a string into an input-statement

        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string without labels or keywords.

        Returns:
            A parsed input-statement.
        """
        name = string
        name = name.strip()
        if len(name) == 0:
            raise TinyLangSyntaxError(line, 'a variable name (to store the input value) is expected!')
        name = check_name_legal(line, name)
        return InputStatement(name)
    
    def exec(self, line, interpreter):
        """ Wait to receive an input from the outside and assign it to a variable.
        
        Args:
            line: The line number of this string, used for error locating.
            interpreter: The interpreter, though which to receive the input.
        """
        value = interpreter.input()
        try:
            value = float(value)
        except ValueError:
            raise IllegalInputError(line)
        interpreter.context[self.name] = value


class PrintStatement(Statement):
    """ A statement that sends an output to the outside though the interpreter. """
    
    def __init__(self, *expr_list):
        """
        Args:
            expr_list: A list of expressions, the value of which will be print out.
                It can be empty, indicating that nothing to print.
        """
        self.expr_list = expr_list
    
    @staticmethod
    def parse(line, string):
        """ Parse a string into a print-statement

        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string without labels or keywords.
                It can be an empty string when there is nothing to print.

        Returns:
            A parsed print-statement.
        """
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
                raise TinyLangSyntaxError(line, 'an expression or value is expected')
            expr_list.append(Expression.parse(line, segment))
        
        return PrintStatement(*expr_list)
    
    def exec(self, line, interpreter):
        """ Evaluate the expressions and print the results to the outside.
        
        Args:
            line: The line number of this string, used for error locating.
            interpreter: The interpreter, though which to receive the input.
        """
        if len(self.expr_list) > 0:
            interpreter.print(self.expr_list[0].eval(line, interpreter.context))
            for expr in self.expr_list[1:]:
                interpreter.print(' ')
                interpreter.print(expr.eval(line, interpreter.context))
        interpreter.print('\n')


# expression

class Expression(abc.ABC):
    
    @staticmethod
    def parse(line, string: str):
        for cls in [ValueExpression, OperatorExpression, ReferenceExpression]:
            try:
                return cls.parse(line, string)
            except TinyLangSyntaxError:
                pass
        raise TinyLangSyntaxError(line, 'Can not parse "' + string + '" as an expression!')
    
    @abc.abstractmethod
    def eval(self, line, context):
        pass


class ValueExpression(Expression):
    def __init__(self, value):
        self.value = value
    
    @staticmethod
    def parse(line, string: str):
        string = string.strip()
        if string.startswith('"') and string.endswith('"'):
            value = string.strip('"')
            return ValueExpression(value)
        if string.replace('.', '', 1).isdigit():
            value = float(string)
            return ValueExpression(value)
        raise TinyLangSyntaxError(line, "Can not parse the string as neither a float number nor a string!")
    
    def eval(self, line, context):
        return self.value


class ReferenceExpression(Expression):
    def __init__(self, name):
        self.name = name
    
    @staticmethod
    def parse(line, string: str):
        name = string.strip()
        name = check_name_legal(line, name)
        return ReferenceExpression(name)
    
    def eval(self, line, context):
        value = context.get(self.name)
        if value is None:
            raise UndefinedVariableError(line, self.name)
        return value


class OperatorExpression(Expression):
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
        # Some operators can contains each other, for example "<=" contains "<".
        # To avoid confusion, we firstly rearrangement the sequence:
        # check operators with bigger length firstly.
        operators = sorted(
            (op for op in OperatorExpression.Operator),
            key=lambda op: len(op.value[0]), reverse=True)
        
        # Try to find an operator.
        operator_pos = -1
        operator = None
        for op in operators:
            s, _ = op.value
            operator_pos = string.find(s)
            if operator_pos != -1:
                operator = op
                break
        
        # If not found any operator, raise an error.
        if operator_pos == -1 or operator is None:
            raise TinyLangSyntaxError(line, "Not found any operator in the expression!")
        
        # If found the operator, parse the expressions on both sides
        op_str, _ = operator.value
        expr1 = string[:operator_pos]
        expr2 = string[operator_pos + len(op_str):]
        expr1 = Expression.parse(line, expr1)
        expr2 = Expression.parse(line, expr2)
        
        return OperatorExpression(operator, expr1, expr2)
    
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
    """ Split the first segment using the specified separator, considering quotes.
    
    This function splits the string by the first not quoted separator.
    
    Args:
        string: The string to be split.
        sep: Several chars by which to separate the string.
        quote: Several chars which is recognized as quote.
    
    Returns:
        A tuple with two split parts.
            If not found any separator outside the quotes,
            the first part will be None, and the second will be the original string
    """
    
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
    """ Split string by the specified separator, considering quotes.
    
    This function has the similar behavior as str.split(). Only it can consider the quotes.
    That is, the separators that between two quotes are not recognized as effective separators.
    
    Args:
        string: The string to be split.
        sep: Several chars by which to separate the string.
        quote: Several chars which is recognized as quote.
    
    Returns:
        A tuple with two elements.
            The first element is the split parts.
            The second element is a boolean that indicates whether the quote is closed.
    """
    
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
    """ Check the name is legal, raises TinyLangSyntaxError if is not.
    
    It contains the following several checks:
     - blank or empty
     - number starting
     - space containing
     - punctuation containing
     - operator containing
    
    """
    
    name = name.strip()
    if len(name) == 0:
        raise TinyLangSyntaxError(line, "name of variables and labels must not be blank or empty!")
    
    if name[0] in '0123456789':
        raise TinyLangSyntaxError(line, "name of variables and labels must not starts with numbers!")
    
    message = '"' + name + '" is not a legal name of variable (label), it must not contains '
    if any(c in name for c in ' \t'):
        raise TinyLangSyntaxError(line, message + "spaces or tabs!")
    if any(c in name for c in ',.:;\'"!@#$%^&?|\\~`'):
        raise TinyLangSyntaxError(line, message + "punctuations! (besides the underscore)")
    if any(c in name for c in '+-*/<=>'):
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
