# Bastors (BAS-to-RS)

Bastors is a toy transpiler, written in Python, that takes a TinyBasic dialect as input and generates Rust code. It is a toy, partly, because its primary objective is to make me more comfortable writing Python code. And partly because it makes no effort to generate any kind of idiomatic Rust code.



## How do I use it?

```
usage: bastors.py [-h] [-o OUTPUT] input
```
### Example

Consider ```programs/fibonacci.bas```:

```
        LET A=0
        LET B=1
    100 PRINT A
        LET B=A+B
        LET A=B-A
        IF B<=1000 THEN GOTO 100
        END
```

This can be transpiled to Rust with this invocation:

```
$ ./bastors.py programs/fibonacci.bas 
struct State {
    a: i32,
    b: i32,
}

fn main() {
    let mut state: State = State {
        a: 0,
        b: 0,
    };
    state.a = 0;
    state.b = 1;
    loop {
        println!("{}", state.a);
        state.b = state.a + state.b;
        state.a = state.b - state.a;
        if state.b > 1000 {
            break;
        }
    }
}
```

Or it can be output to file, and later compiled using rustc:

```
$ ./bastors.py programs/fibonacci.bas -o fib.rs
$ rustc fib.rs
$ ./fib
0
1
1
2
3
5
8
13
21
34
55
89
144
233
377
610
```

## GOTO Elimination
It turns out that the lion share of this project was about how to deal with the GOTO statement.
Since Rust does not have any concept of GOTO and Basic relies quite heavily on it. I ended up following the GOTO elimination algorithms found at [DZone](https://dzone.com/articles/goto-elimination-algorithm).

This splits up the usage of GOTO into different cases and provides strategies to deal with them. You can read more about the algorithms at the link above or in comments in goto_elimimination.py.

It makes no attempt to create beautiful code. For instance, here is a game called *Hunt The hurkle* written by [Damian Walker](http://damian.cyningstan.org.uk/post/130/hunt-the-hurkle-another-tiny-basic-game):
```
    REM
    REM Hunt the Hurkle
    REM A Demonstration Program for Tiny BASIC
    REM Copyright Damian Walker
    REM http://damian.cyningstan.org.uk/post/130/hunt-the-hurkle-another-tiny-basic-game
    REM

    REM --- Variables
    REM     G: hurkle column
    REM     H: hurkle row
    REM     M: moves taken
    REM     S: random number seed
    REM     X: player guess column
    REM     Y: player guess row

    REM --- Initialise the random number generator
    PRINT "Think of a number."
    INPUT S

    REM --- Initialise the game
    GOSUB 200
    LET G=R-(R/10*10)
    GOSUB 200
    LET H=R-(R/10*10)
    LET M=0

    REM --- Input player guess
 10 PRINT "Where is the hurkle? Enter column then row."
    INPUT X,Y
    IF X>=0 THEN IF X<=9 THEN IF Y>=0 THEN IF Y<=9 THEN GOTO 20
    PRINT "That location is off the grid!"
    GOTO 10

    REM --- Process player guess
 20 LET M=M+1
    PRINT "The Hurkle is..."
    IF G<X THEN IF H<Y THEN PRINT "...to the northwest."
    IF G=X THEN IF H<Y THEN PRINT "...to the north."
    IF G>X THEN IF H<Y THEN PRINT "...to the northeast."
    IF G>X THEN IF H=Y THEN PRINT "...to the east."
    IF G>X THEN IF H>Y THEN PRINT "...to the southeast."
    IF G=X THEN IF H>Y THEN PRINT "...to the south."
    IF G<X THEN IF H>Y THEN PRINT "...to the southwest."
    IF G<X THEN IF H=Y THEN PRINT "...to the west."
    IF G=X THEN IF H=Y THEN GOTO 40
    IF M>6 THEN GOTO 50
    PRINT "You have taken ",M," turns so far."
    GOTO 10

    REM --- Player has won
 40 PRINT "...RIGHT HERE!"
    PRINT "You took ",M," turns to find it."
    END
    
    REM --- Player has lost
 50 PRINT "You have taken too long over this. You lose!"
    END

    REM --- Random number generator
200 LET S=(42*S+127)-((42*S+127)/126*126)
    LET R=S
    RETURN
```

And the generated Rust:

```
use std::io;
struct State {
    g: i32,
    h: i32,
    m: i32,
    r: i32,
    s: i32,
    t1: bool,
    t2: bool,
    t3: bool,
    x: i32,
    y: i32,
}

fn f_200(state: &mut State) {
    state.s = (42 * state.s + 127) - ((42 * state.s + 127) / 126 * 126);
    state.r = state.s;
    return;
}

fn main() {
    let mut state: State = State {
        g: 0,
        h: 0,
        m: 0,
        r: 0,
        s: 0,
        t1: false,
        t2: false,
        t3: false,
        x: 0,
        y: 0,
    };
    println!("{}", "Think of a number.");
    loop {
        let mut input = String::new();
        io::stdin().read_line(&mut input).unwrap();
        match input.trim().parse::<i32>() {
            Ok(i) => {
                state.s = i;
                break;
            }
            Err(_) => println!("invalid number"),
        }
    }
    f_200(&mut state);
    state.g = state.r - (state.r / 10 * 10);
    f_200(&mut state);
    state.h = state.r - (state.r / 10 * 10);
    state.m = 0;
    loop {
        loop {
            println!("{}", "Where is the hurkle? Enter column then row.");
            loop {
                let mut input = String::new();
                io::stdin().read_line(&mut input).unwrap();
                match input.trim().parse::<i32>() {
                    Ok(i) => {
                        state.x = i;
                        break;
                    }
                    Err(_) => println!("invalid number"),
                }
            }
            loop {
                let mut input = String::new();
                io::stdin().read_line(&mut input).unwrap();
                match input.trim().parse::<i32>() {
                    Ok(i) => {
                        state.y = i;
                        break;
                    }
                    Err(_) => println!("invalid number"),
                }
            }
            if state.x < 0 || state.x > 9 || state.y < 0 || state.y > 9 {
                println!("{}", "That location is off the grid!");
                state.t1 = true;
            }
            state.t3 = false;
            if !state.t1 {
                break;
            }
        }
        state.m = state.m + 1;
        println!("{}", "The Hurkle is...");
        if state.g < state.x && state.h < state.y {
            println!("{}", "...to the northwest.");
        }
        if state.g == state.x && state.h < state.y {
            println!("{}", "...to the north.");
        }
        if state.g > state.x && state.h < state.y {
            println!("{}", "...to the northeast.");
        }
        if state.g > state.x && state.h == state.y {
            println!("{}", "...to the east.");
        }
        if state.g > state.x && state.h > state.y {
            println!("{}", "...to the southeast.");
        }
        if state.g == state.x && state.h > state.y {
            println!("{}", "...to the south.");
        }
        if state.g < state.x && state.h > state.y {
            println!("{}", "...to the southwest.");
        }
        if state.g < state.x && state.h == state.y {
            println!("{}", "...to the west.");
        }
        if state.g != state.x || state.h != state.y {
            state.t2 = state.m > 6;
            if !state.t2 {
                println!("{}{}{}", "You have taken ", state.m, " turns so far.");
                state.t3 = true;
            }
        }
        if !state.t3 {
            break;
        }
    }
    if !state.t2 {
        println!("{}", "...RIGHT HERE!");
        println!("{}{}{}", "You took ", state.m, " turns to find it.");
        return;
    }
    println!("{}", "You have taken too long over this. You lose!");
    return;
}

```

## Help me make this Pythonic
A big reason for me to write this tool is to improve my Python. Any help would be greatly appreciated! Tell me what data structures I misused! Or which I should use instead! Tell me about best practices I missed, both in code and in how I set the project up!

Any and all code review would be very kind!

## Running tests
Bastors includes tests that aim to make development easier. It will test the lexing-, parsing-, GOTO elimination- and rustification phases. The tests can be run by running ```make test```.

## TinyBasic Grammar
The grammar understood for this TinyBasic is as follows:
```
    line ::= number statement CR | statement CR
    statement ::= PRINT expr-list
                  IF expression operator expression THEN statement
                  GOTO number
                  INPUT var-list
                  LET var = expression
                  GOSUB number
                  RETURN
                  CLEAR
                  LIST
                  RUN
                  END
    expr-list ::= (string|expression) (, (string|expression) )*
    var-list ::= var (, var)*
    expression ::= term ((+|-) term)*
    term ::= factor ((*|/) factor)*
    factor ::= var | number | (expression)
    var ::= A | B | C ... | Y | Z
    number ::= digit digit*
    digit ::= 0 | 1 | 2 | 3 | ... | 8 | 9
    operator ::= < (>|=|ε) | > (<|=|ε) | =
    string ::= " (a|b|c ... |x|y|z|A|B|C ... |X|Y|Z|digit)* " """
```

## Contribute
If for any reason you find this neat and want to contribute, please feel free! A good way would be to find and add Basic programs you wish could be transpiled to the program/ directory. The test harness will make sure all programs found there will stay compile-able. If you find a program that does not transpile or compile, please file an issue and maybe it can be fixed!

Another way would be to make the Rust code better. To do away with the big State structure mayhaps? And instead only pass the variables needed? Or maybe make the TinyBasic language handle expressions as GOTO or GOSUB targets? Or making sure comments end up in nice places in the Rust code? Or adding RND() or other neat functions?

Maybe you want to convert some old graphics stuff? That uses PUT to draw pixels? And convert that into some Rust canvas thingies? Sounds cool.
