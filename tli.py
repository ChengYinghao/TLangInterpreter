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
                try:
                    statement.exec(this_line, self)
                except TinyLangRuntimeError:
                    raise
                except RuntimeError as e:
                    raise UnknownCompileError(this_line, e)
    
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
        
        """
        self.load_string(string, keep_empty)
        self.resume()


# statement

class Statement(abc.ABC):
    """ An executable component of tiny-lang code.
    
    A statement is some code that can be executed.
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
    """ A evaluable component of tiny-lang code.
    
    An expression is some code that can be evaluated.
    The evaluated of a statement returns a value.
    
    There 3 types of expression
     - value expression: a constant value
     - reference statement: a reference to a variable
     - operator statement: a operation of some other expressions

    """
    
    @staticmethod
    def parse(line, string: str):
        """ Parse a string into a tiny-lang expression.

        This function can detect the type of expression and parse it in a right way.

        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string to be parsed.

        Returns:
            A parsed typed statement.
        """
        
        # Try to parse the string into every type by sequence
        for cls in [ValueExpression, OperatorExpression, ReferenceExpression]:
            try:
                # return if successfully parsed
                return cls.parse(line, string)
            except TinyLangSyntaxError:
                # try the next type if failed
                pass
        
        # raise a syntax error if no any success
        raise TinyLangSyntaxError(line, 'Can not parse "' + string + '" as an expression!')
    
    @abc.abstractmethod
    def eval(self, line, context):
        """ Evaluate the expression.
        
        This is an abstract method. It should be implemented in subclasses.
        
        Args:
            line: The line number of this string, used for error locating.
            context: The context that contains all runtime variables.
            
        """
        pass


class ValueExpression(Expression):
    """ An expression that holds a constant value. """
    
    def __init__(self, value):
        """
        Args:
            value: The constant to be hold
        """
        self.value = value
    
    @staticmethod
    def parse(line, string: str):
        """ Parse a string into a value expression.
        
        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string to be parsed.
        
        Returns:
            A parsed value statement.
        """
        string = string.strip()
        
        # try to parse as a string
        if string.startswith('"') and string.endswith('"'):
            value = string.strip('"')
            return ValueExpression(value)
        
        # try to parse as a float
        try:
            value = float(string)
            return ValueExpression(value)
        except ValueError:
            pass
        
        # raise if not successfully parsed
        raise TinyLangSyntaxError(line, "Can not parse the string as neither a float number nor a string!")
    
    def eval(self, line, context):
        """ Simply return the holding constant value
        
        Args:
            line: The line number of this string, used for error locating.
            context: The context that contains all runtime variables.
        """
        return self.value


class ReferenceExpression(Expression):
    """ An expression that refers to a variable. """
    
    def __init__(self, name):
        """
        Args:
            name: Name of the referred variable.
        """
        self.name = name
    
    @staticmethod
    def parse(line, string: str):
        """ Parse a string into a reference expression.
        
        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string to be parsed.
        
        Returns:
            A parsed reference statement.
        """
        name = string.strip()
        name = check_name_legal(line, name)
        return ReferenceExpression(name)
    
    def eval(self, line, context):
        """ Return the value of the referred variable
        
        Args:
            line: The line number of this string, used for error locating.
            context: The context that contains all runtime variables.
        """
        
        # Get the variable value by name
        value = context.get(self.name)
        
        # Raise if not found the variable
        if value is None:
            raise UndefinedVariableError(line, self.name)
        
        return value


class OperatorExpression(Expression):
    """ An expression that indicates an operation of some other expression.
    
    Tiny-lang supported only binary operator.
    So an operator expression has only two operands.
    
    The supported operations are listed below:
     - plus (+)
     - minus (-)
     - times (*)
     - divide (/)
     - less than (<)
     - less than or equal (<=)
     - more than (>)
     - more than or equal (>=)
     - equal (==)
     - not equal (!=)
    """
    
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
        """
        Args:
            operator: The operator of this expression, it should be a member of the Operator Enum
            expr1: The first operand of the operation
            expr2: The second operand of the operation
        """
        self.operator = operator
        self.expr1 = expr1
        self.expr2 = expr2
    
    @staticmethod
    def parse(line, string: str):
        """ Parse a string into a reference expression.
        
        Args:
            line: The line number of this string, used for error locating.
            string: A one-line string to be parsed.
        
        Returns:
            A parsed reference statement.
        """
        
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
        """ Evaluate the operands, perform the operation and return the result

        Args:
            line: The line number of this string, used for error locating.
            context: The context that contains all runtime variables.
        """
        
        # evaluate the values of the operands
        x = self.expr1.eval(line, context)
        y = self.expr2.eval(line, context)
        
        # perform the operation and return the result
        _, func = self.operator.value
        return func(x, y)


# runtime error

class TinyLangRuntimeError(RuntimeError):
    def __init__(self, line, message):
        message += " (at line " + str(line) + ")"
        super().__init__(message)
        self.line = line


class UnknownRuntimeError(TinyLangRuntimeError):
    def __init__(self, line, error):
        self.error = error
        message = "Unknown runtime error: interpreter stopped due to the following unrecognized error!"
        super().__init__(line, message)
    
    def __str__(self) -> str:
        return super().__str__() + "\n" + str(self.error)


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
    
    # Find the position of the first "legal" separator in a while loop.
    cursor = 0
    while True:
        # Find next quote and next separator
        quote_pos = string.find(quote, cursor)
        sep_pos = string.find(sep, cursor)
        
        # If not found any separator, break the loop as not found
        if sep_pos == -1:
            break
        
        # If not found any quote, just use the found separator
        if quote_pos == -1:
            break
        
        # If the separator is in front of the quote, just use the found separator
        if sep_pos < quote_pos:
            break
        
        # Find the closing quote, set the cursor after it and find again
        closing_quote_pos = string.find(quote, quote_pos + 1)
        if closing_quote_pos == -1:
            sep_pos = -1
            break
        cursor = closing_quote_pos + 1
    
    if sep_pos != -1:
        # If a "legal" separator is found, return the split parts
        return string[:sep_pos], string[sep_pos + len(sep):]
    else:
        # If not found any "legal" separator, return None and the origin string
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
    
    # Firstly split the string by quotes
    quote_segments = string.split(quote)
    
    # Split the first non-quoted quote_segment
    quoted = False
    segments = quote_segments[0].split(sep)
    
    # For the other quote_segments, split only the non-quoted ones
    for i, quote_segment in enumerate(quote_segments[1:]):
        # Starting from the index 1, the even quote_segments are quoted
        quoted = i % 2 == 0
        if quoted:
            # If quoted, simply concatenate it to the last split segment
            segments[-1] += quote + quote_segment
        else:
            # If not quoted, split the quote_segment by the separator
            sep_segments = quote_segment.split(sep)
            
            # Concatenate the first sep_segment to the last split segment
            segments[-1] += quote + sep_segments[0]
            
            # Simply extend other sep_segments to the split segments list
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
    
    Args:
        line: The line number of this string, used for error locating.
        name: The name to be checked
    
    Returns:
        A stripped legal name
    
    """
    
    # Check the name is blank or empty
    name = name.strip()
    if len(name) == 0:
        raise TinyLangSyntaxError(line, "name of variables and labels must not be blank or empty!")
    
    # Check if the name starts with any number
    if name[0] in '0123456789':
        raise TinyLangSyntaxError(line, "name of variables and labels must not starts with numbers!")
    
    # Check if the name contains any illegal chars
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
    """ The "main function" of this python script """
    
    # Read the arguments
    args = sys.argv
    
    # The first argument should be the working dir
    work_dir = args[0]
    os.chdir(os.path.dirname(work_dir))
    
    # Check the mode
    if len(args) == 1:
        # If not any extra arguments, run in interactive mode
        main_interactive()
    elif len(args) == 2:
        # If given the second argument, run in script mode,
        # The second argument is taken as a script filename.
        script_fn = args[1]
        main_script(script_fn)
    else:
        # Raise if given more arguments
        raise RuntimeError("Expected 1 parameter or no parameters, given " + str(len(args) - 1) + ".")


def main_interactive():
    """ The "main function" in interactive mode """
    
    # initialize an interpreter
    interpreter = TinyLangInterpreter()
    
    # receive any input from stdin
    break_error = None
    while True:
        try:
            # read the input string and execute it
            string = input('Line[' + str(interpreter.next_line) + '] > ')
            interpreter.execute_string(string, keep_empty=False)
        except TinyLangCompileError as e:
            # skip when meeting any compile error
            print(e)
            continue
        except TinyLangRuntimeError as e:
            # break and record when meeting any runtime error
            break_error = e
            break
        except EOFError:
            # break when meeting the end
            break
    
    # finalization
    print()
    if break_error is not None:
        # if recorded any error, print it out
        print("Terminated with error:")
        print(break_error)
    else:
        # if no recorded any error, just print the word "Finished"
        print("Finished.")


def main_script(script_fn):
    """ The "main function" in script mode """
    
    # read the script file
    try:
        with open(script_fn, 'r') as script_file:
            string = script_file.read()
    except IOError as e:
        print("Failed to read the script file!")
        print(e)
    
    # initialize an interpreter
    interpreter = TinyLangInterpreter()
    
    # run the script
    interpreter.execute_string(string, keep_empty=True)


if __name__ == '__main__':
    main()
