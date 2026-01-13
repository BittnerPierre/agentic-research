---
title: ""Hello, World!" program"
source: "https://en.wikipedia.org/wiki/%22Hello,_World!%22_program"
content_length: 43970
---

# "Hello, World!" program

**Source:** [https://en.wikipedia.org/wiki/%22Hello,_World!%22_program](https://en.wikipedia.org/wiki/%22Hello,_World!%22_program)

## Contenu

From Wikipedia, the free encyclopedia
Traditional first example of a computer programming language
"Hello, World" and "Helloworld" redirect here. For other uses, see [Hello World (disambiguation)](</wiki/Hello_World_\(disambiguation\)> "Hello World \(disambiguation\)").
A
* "Hello, World!" program
* is usually a simple [computer program](</wiki/Computer_program> "Computer program") that emits (or displays) to the screen (often the [console](</wiki/Console_application> "Console application")) a message similar to "Hello, World!". A small piece of code in most [general-purpose programming languages](</wiki/General-purpose_programming_language> "General-purpose programming language"), this program is used to illustrate a language's basic [syntax](</wiki/Syntax_\(programming_languages\)> "Syntax \(programming languages\)"). Such a program is often the first written by a student of a new programming language,[1] but it can also be used as a [sanity check](</wiki/Sanity_check> "Sanity check") to ensure that the [computer software](</wiki/Computer_software> "Computer software") intended to [compile](</wiki/Compiler> "Compiler") or run [source code](</wiki/Source_code> "Source code") is correctly installed, and that its operator understands how to use it.
## History
[[edit](</w/index.php?title=%22Hello,_World!%22_program&action=edit&section=1> "Edit section: History")]
[](</wiki/File:Hello_World_Brian_Kernighan_1978.jpg>)"Hello, World!" program handwritten in the [C language](</wiki/C_\(programming_language\)> "C \(programming language\)") and signed by [Brian Kernighan](</wiki/Brian_Kernighan> "Brian Kernighan") (1978)
While several small test programs have existed since the development of programmable [computers](</wiki/Computer> "Computer"), the tradition of using the phrase "Hello, World!" as a test message was influenced by an example program in the 1978 book _[The C Programming Language](</wiki/The_C_Programming_Language> "The C Programming Language")_ ,[2] with likely earlier use in [BCPL](</wiki/BCPL> "BCPL"). The example program from the book prints "hello, world", and was inherited from a 1974 [Bell Laboratories](</wiki/Bell_Labs> "Bell Labs") internal memorandum by [Brian Kernighan](</wiki/Brian_Kernighan> "Brian Kernighan"), _Programming in C: A Tutorial_ :[3]
```
main( ) {
printf("hello, world");
}
```
In the above example, the main( ) [function](</wiki/Subroutine> "Subroutine") defines where the program [should start executing](</wiki/Entry_point> "Entry point"). The function body consists of a single [statement](</wiki/Statement_\(computer_science\)> "Statement \(computer science\)"), a call to the printf() function, which stands for "_print f_ ormatted"; it outputs to the [console](</wiki/Console_application> "Console application") whatever is passed to it as the [parameter](</wiki/Parameter_\(computer_programming\)> "Parameter \(computer programming\)"), in this case the [string](</wiki/String_\(computer_science\)> "String \(computer science\)") "hello, world".
The C-language version was preceded by Kernighan's own 1972 _A Tutorial Introduction to the Language[B](</wiki/B_\(programming_language\)> "B \(programming language\)")_,[4] where the first known version of the program is found in an example used to illustrate external variables:
```
main( ) {
extrn a, b, c;
putchar(a); putchar(b); putchar(c); putchar('!*n');
}
a 'hell';
b 'o, w';
c 'orld';
```
The program above prints _hello, world!_ on the terminal, including a [newline](</wiki/Newline> "Newline") character. The phrase is divided into multiple variables because in B a character constant is limited to four [ASCII](</wiki/ASCII> "ASCII") characters. The previous example in the tutorial printed _hi!_ on the terminal, and the phrase _hello, world!_ was introduced as a slightly longer greeting that required several character constants for its expression.
The [Jargon File](</wiki/Jargon_File> "Jargon File") reports that "hello, world" instead originated in 1967 with the language [BCPL](</wiki/BCPL> "BCPL").[5] Outside computing, use of the exact phrase began over a decade prior; it was the [catchphrase](</wiki/Catchphrase> "Catchphrase") of New York radio disc jockey [William B. Williams](</wiki/William_B._Williams_\(DJ\)> "William B. Williams \(DJ\)") beginning in the 1950s.[6]
## Variations
[[edit](</w/index.php?title=%22Hello,_World!%22_program&action=edit&section=2> "Edit section: Variations")]
[](</wiki/File:PSP-Homebrew.jpeg>)A "Hello, World!" program running on Sony's [PlayStation Portable](</wiki/PlayStation_Portable_homebrew> "PlayStation Portable homebrew") as a [proof of concept](</wiki/Proof_of_concept> "Proof of concept")
"Hello, World!" programs vary in complexity between different languages. In some languages, particularly [scripting languages](</wiki/Scripting_language> "Scripting language"), the "Hello, World!" program can be written as one statement, while in others (more so many [low-level languages](</wiki/Low-level_programming_language> "Low-level programming language")) many more statements can be required. For example, in [Python](</wiki/Python_\(programming_language\)> "Python \(programming language\)"), to print the string _Hello, World!_ followed by a newline, one only needs to write `print("Hello, World!")`. In contrast, the equivalent code in [C++](</wiki/C%2B%2B> "C++")[7] requires the import of the [C++ standard library](</wiki/C%2B%2B_standard_library> "C++ standard library"), the declaration of an [entry point](</wiki/Entry_point> "Entry point") (main function), and a call to print a line of text to the standard output stream.
[](</wiki/File:CNC_Hello_World.jpg>)Computer [numerical control](</wiki/Numerical_control> "Numerical control") (CNC) machining test in [poly(methyl methacrylate)](</wiki/Poly\(methyl_methacrylate\)> "Poly\(methyl methacrylate\)") (Perspex)
The phrase "Hello, World!" has seen various deviations in casing and punctuation, such as "hello world" which lacks the capitalization of the leading _H_ and _W_ , and the presence of the comma or exclamation mark. Some devices limit the format to specific variations, such as all-capitalized versions on systems that support only capital letters, while some [esoteric programming languages](</wiki/Esoteric_programming_language> "Esoteric programming language") may have to print a slightly modified string. Other human languages have been used as the output; for example, a tutorial for the [Go language](</wiki/Go_\(programming_language\)> "Go \(programming language\)") emitted both English and Chinese or Japanese characters, demonstrating the language's built-in [Unicode](</wiki/Unicode> "Unicode") support.[8] Another notable example is the [Rust language](</wiki/Rust_\(programming_language\)> "Rust \(programming language\)"), whose management system automatically inserts a "Hello, World" program when creating new projects.
[](</wiki/File:HelloWorld_Maktivism_ComputerProgramming_LEDs.jpg>)A "Hello, World!" message being displayed through long-exposure [light painting](</wiki/Light_painting> "Light painting") with a moving strip of [light-emitting diodes](</wiki/Light-emitting_diode> "Light-emitting diode") (LEDs)
Some languages change the function of the "Hello, World!" program while maintaining the spirit of demonstrating a simple example. [Functional programming](</wiki/Functional_programming> "Functional programming") languages, such as [Lisp](</wiki/Lisp_\(programming_language\)> "Lisp \(programming language\)"), [ML](</wiki/ML_\(programming_language\)> "ML \(programming language\)"), and [Haskell](</wiki/Haskell> "Haskell"), tend to substitute a [factorial](</wiki/Factorial> "Factorial") program for "Hello, World!", as functional programming emphasizes recursive techniques, whereas the original examples emphasize I/O, which violates the spirit of pure functional programming by producing [side effects](</wiki/Side_effect_\(computer_science\)> "Side effect \(computer science\)"). Languages otherwise able to print "Hello, World!" ([assembly language](</wiki/Assembly_language> "Assembly language"), [C](</wiki/C_\(programming_language\)> "C \(programming language\)"), [VHDL](</wiki/VHDL> "VHDL")) may also be used in [embedded systems](</wiki/Embedded_system> "Embedded system"), where text output is either difficult (requiring added components or communication with another computer) or nonexistent. For devices such as [microcontrollers](</wiki/Microcontroller> "Microcontroller"), [field-programmable gate arrays](</wiki/Field-programmable_gate_array> "Field-programmable gate array"), and [complex programmable logic devices](</wiki/Complex_programmable_logic_device> "Complex programmable logic device") (CPLDs), "Hello, World!" may thus be substituted with a blinking [light-emitting diode](</wiki/Light-emitting_diode> "Light-emitting diode") (LED), which demonstrates timing and interaction between components.[9][10][11][12][13]
The [Debian](</wiki/Debian> "Debian") and [Ubuntu](</wiki/Ubuntu> "Ubuntu") [Linux distributions](</wiki/Linux_distribution> "Linux distribution") provide the "Hello, World!" program through their [software package manager](</wiki/Package_manager> "Package manager") systems, which can be invoked with the command _hello_. It serves as a [sanity check](</wiki/Sanity_check> "Sanity check") and a simple example of installing a software package. For developers, it provides an example of creating a [.deb](</wiki/.deb> ".deb") package, either traditionally or using _debhelper_ , and the version of hello used, [GNU Hello](</wiki/GNU_Hello> "GNU Hello"), serves as an example of writing a [GNU](</wiki/GNU> "GNU") program.[14]
Variations of the "Hello, World!" program that produce a [graphical output](</wiki/Computer_graphics> "Computer graphics") (as opposed to text output) have also been shown. [Sun](</wiki/Sun_Microsystems> "Sun Microsystems") demonstrated a "Hello, World!" program in [Java](</wiki/Java_\(programming_language\)> "Java \(programming language\)") based on [scalable vector graphics](</wiki/Scalable_vector_graphics> "Scalable vector graphics"),[15] and the [XL](</wiki/XL_\(programming_language\)> "XL \(programming language\)") programming language features a spinning Earth "Hello, World!" using [3D computer graphics](</wiki/3D_computer_graphics> "3D computer graphics").[16] Mark Guzdial and [Elliot Soloway](</w/index.php?title=Elliot_Soloway&action=edit&redlink=1> "Elliot Soloway \(page does not exist\)") have suggested that the "hello, world" test message may be outdated now that graphics and sound can be manipulated as easily as text.[17]
In [computer graphics](</wiki/Computer_graphics> "Computer graphics"), rendering a triangle – called "Hello Triangle" – is sometimes used as an introductory example for [graphics libraries](</wiki/Graphics_library> "Graphics library").[18][19]
## Time to Hello World
[[edit](</w/index.php?title=%22Hello,_World!%22_program&action=edit&section=3> "Edit section: Time to Hello World")]
"Time to hello world" (TTHW) is the time it takes to author a "Hello, World!" program in a given programming language. This is one measure of a programming language's ease of use. Since the program is meant as an introduction for people unfamiliar with the language, a more complex "Hello, World!" program may indicate that the programming language is less approachable.[20] For instance, the first publicly known "Hello, World!" program in [Malbolge](</wiki/Malbolge> "Malbolge") (which actually output "HEllO WORld") took two years to be announced, and it was produced not by a human but by a code generator written in [Common Lisp](</wiki/Common_Lisp> "Common Lisp") (see § Variations, above).
The concept has been extended beyond programming languages to [APIs](</wiki/Application_programming_interface> "Application programming interface"), as a measure of how simple it is for a new developer to get a basic example working; a shorter time indicates an easier API for developers to adopt.[21][22]
## Wikipedia articles containing "Hello, World!" programs
[[edit](</w/index.php?title=%22Hello,_World!%22_program&action=edit&section=4> "Edit section: Wikipedia articles containing "Hello, World!" programs")]
* [ABAP](</wiki/ABAP#Hello_world> "ABAP")
* [Ada](</wiki/Ada_\(programming_language\)#"Hello,_world!"_in_Ada> "Ada \(programming language\)")
* [Aldor](</wiki/Aldor#Examples> "Aldor")
* [ALGOL](</wiki/ALGOL#Timeline:_Hello_world> "ALGOL")
* [ALGOL 60](</wiki/ALGOL_60> "ALGOL 60")
* [AmbientTalk](</wiki/AmbientTalk#Hello_world> "AmbientTalk")
* [Amiga E](</wiki/Amiga_E#"Hello,_World!"_example> "Amiga E")
* [Apache Click](</wiki/Apache_Click#Example> "Apache Click")
* [Apache Jelly](</wiki/Apache_Jelly#Usage> "Apache Jelly")
* [Apache Wicket](</wiki/Apache_Wicket#Example> "Apache Wicket")
* [AppJar](</wiki/AppJar#Example> "AppJar")
* [AppleScript](</wiki/AppleScript#Hello,_world!> "AppleScript")
* [Applesoft BASIC](</wiki/Applesoft_BASIC#Sample_code> "Applesoft BASIC")
* [Arc](</wiki/Arc_\(programming_language\)#Examples> "Arc \(programming language\)")
* [Atari Assembler Editor](</wiki/Atari_Assembler_Editor#Example_code> "Atari Assembler Editor")
* [AutoLISP](</wiki/AutoLISP#Examples> "AutoLISP")
* [AviSynth](</wiki/AviSynth#"Hello_World"> "AviSynth")
* [AWK](</wiki/AWK#Hello_World> "AWK")
* [BASIC](</wiki/BASIC#Examples> "BASIC")
* [Basic Assembly Language](</wiki/Basic_Assembly_Language#Examples> "Basic Assembly Language")
* [Ballerina](</wiki/Ballerina_\(programming_language\)#Hello_World> "Ballerina \(programming language\)")
* [BCPL](</wiki/BCPL#Hello_world> "BCPL")
* [Beatnik](</wiki/Beatnik_\(programming_language\)#Hello_World> "Beatnik \(programming language\)")
* [Befunge](</wiki/Befunge#Sample_Befunge-93_code> "Befunge")
* [BETA](</wiki/BETA_\(programming_language\)#Hello_world!> "BETA \(programming language\)")
* [Blitz BASIC](</wiki/Blitz_BASIC#Examples> "Blitz BASIC")
* [Brainfuck](</wiki/Brainfuck#Hello_World!> "Brainfuck")
* [C](</wiki/C_\(programming_language\)#"Hello,_world"_example> "C \(programming language\)")
* [Caché ObjectScript](</wiki/Cach%C3%A9_ObjectScript#Caché_programming_examples> "Caché ObjectScript")
* [Cairo](</wiki/Cairo_\(graphics\)#Example> "Cairo \(graphics\)")
* [C/AL](</wiki/C/AL#Hello_World> "C/AL")
* [Carbon](</wiki/Carbon_\(programming_language\)#Example> "Carbon \(programming language\)")
* [Casio BASIC](</wiki/Casio_BASIC#Examples> "Casio BASIC")
* [Charm](</wiki/Charm_\(programming_language\)#Example> "Charm \(programming language\)")
* [CherryPy](</wiki/CherryPy#Pythonic_interface> "CherryPy")
* [Clean](</wiki/Clean_\(programming_language\)#Examples> "Clean \(programming language\)")
* [Clipper](</wiki/Clipper_\(programming_language\)#Programming_in_Clipper> "Clipper \(programming language\)")
* [C++](</wiki/C%2B%2B#Language> "C++")
* [C#](</wiki/C_Sharp_\(programming_language\)#Hello_World> "C Sharp \(programming language\)")
* [COBOL](</wiki/COBOL#Hello,_world> "COBOL")
* [Cobra](</wiki/Cobra_\(programming_language\)#Hello_World> "Cobra \(programming language\)")
* [Common Intermediate Language](</wiki/Common_Intermediate_Language#Example> "Common Intermediate Language")
* [Crystal](</wiki/Crystal_\(programming_language\)#Hello_World> "Crystal \(programming language\)")
* [Cython](</wiki/Cython#Example> "Cython")
* [Dart](</wiki/Dart_\(programming_language\)#Example> "Dart \(programming language\)")
* [Darwin](</wiki/Darwin_\(programming_language\)#Example_Code> "Darwin \(programming language\)")
* [Data General Nova](</wiki/Data_General_Nova#Hello_world_program> "Data General Nova")
* [Deno](</wiki/Deno_\(software\)#Examples> "Deno \(software\)")
* [DOORS Extension Language](</wiki/DOORS_Extension_Language#"Hello,_World"_example> "DOORS Extension Language")
* [Easy Programming Language](</wiki/Easy_Programming_Language#Programming_examples> "Easy Programming Language")
* [Эль-76](</wiki/El-76#Program_sample> "El-76")
* [Elixir](</wiki/Elixir_\(programming_language\)#Examples> "Elixir \(programming language\)")
* [Enyo](</wiki/Enyo_\(software\)#Examples> "Enyo \(software\)")
* [எழில்](</wiki/Ezhil_\(programming_language\)#Hello_world> "Ezhil \(programming language\)")
* [F#](</wiki/F_Sharp_\(programming_language\)#Examples> "F Sharp \(programming language\)")
* [FastAPI](</wiki/FastAPI#Example> "FastAPI")
* [Fjölnir](</wiki/Fj%C3%B6lnir_\(programming_language\)#Code_examples> "Fjölnir \(programming language\)")
* [Flask](</wiki/Flask_\(web_framework\)#Example> "Flask \(web framework\)")
* [Flix](</wiki/Flix_\(programming_language\)#Hello_world> "Flix \(programming language\)")
* [Forth](</wiki/Forth_\(programming_language\)#“Hello,_World!”> "Forth \(programming language\)")
* [FORTRAN](</wiki/Fortran#"Hello,_World!"_example> "Fortran")
* [Fortress](</wiki/Fortress_\(programming_language\)#Example:_Hello_world!> "Fortress \(programming language\)")
* [FreeBASIC](</wiki/FreeBASIC#Example_code> "FreeBASIC")
* [Go](</wiki/Go_\(programming_language\)#Hello_world> "Go \(programming language\)")
* [Godot](</wiki/Godot_\(game_engine\)#GDScript> "Godot \(game engine\)")
* [Google Gadgets](</wiki/Google_Gadgets#Technology> "Google Gadgets")
* [GNU Smalltalk](</wiki/GNU_Smalltalk#Examples> "GNU Smalltalk")
* [Hack](</wiki/Hack_\(programming_language\)#Syntax_and_semantics> "Hack \(programming language\)")
* [Harbour](</wiki/Harbour_\(programming_language\)#Sample_code> "Harbour \(programming language\)")
* [Haskell](</wiki/Haskell#Code_examples> "Haskell")
* [Hollywood](</wiki/Hollywood_\(programming_language\)#Hello_World_program> "Hollywood \(programming language\)")
* [HTML](</wiki/HTML#Markup> "HTML")
* [HTML Application](</wiki/HTML_Application#Example> "HTML Application")
* [IBM Open Class](</wiki/IBM_Open_Class#Examples> "IBM Open Class")
* [Idris](</wiki/Idris_\(programming_language\)#Features> "Idris \(programming language\)")
* [INTERCAL](</wiki/INTERCAL#Hello,_world> "INTERCAL")
* [Internet Foundation Classes](</wiki/Internet_Foundation_Classes#Hello_World> "Internet Foundation Classes")
* [Io](</wiki/Io_\(programming_language\)#Examples> "Io \(programming language\)")
* [IRAF](</wiki/IRAF#IRAF_specific_languages> "IRAF")
* [J](</wiki/J_\(programming_language\)#Examples> "J \(programming language\)")
* [JADE](</wiki/JADE_\(programming_language\)#Hello_World!> "JADE \(programming language\)")
* [Jam.py](</wiki/Jam.py_\(web_framework\)#Example> "Jam.py \(web framework\)")
* [Java](</wiki/Java_\(programming_language\)#Examples> "Java \(programming language\)")
* [JavaFX Script](</wiki/JavaFX_Script#Syntax> "JavaFX Script")
* [JavaScript](</wiki/JavaScript#Simple_examples> "JavaScript")
* [JFace](</wiki/JFace#Example> "JFace")
* [K](</wiki/K_\(programming_language\)#Examples> "K \(programming language\)")
* [KERNAL](</wiki/KERNAL#Example> "KERNAL")
* [Kivy](</wiki/Kivy_\(framework\)#Code_example> "Kivy \(framework\)")
* [K-Meleon](</wiki/K-Meleon#Customization> "K-Meleon")
* [LibreLogo](</wiki/LibreLogo#Hello_world_example> "LibreLogo")
* [Lisp](</wiki/Lisp_\(programming_language\)#Examples> "Lisp \(programming language\)")
* [LiveScript](</wiki/LiveScript_\(programming_language\)#Syntax> "LiveScript \(programming language\)")
* [LOLCODE](</wiki/LOLCODE#Language_structure_and_examples> "LOLCODE")
* [Lua](</wiki/Lua_\(programming_language\)#Syntax> "Lua \(programming language\)")
* [MAC/65](</wiki/MAC/65#MAC/65_ToolKit> "MAC/65")
* [MACRO-10](</wiki/MACRO-10#Programming_examples> "MACRO-10")
* [MACRO-11](</wiki/MACRO-11#Programming_example> "MACRO-11")
* [MAD](</wiki/MAD_\(programming_language\)#"Hello,_world"_example> "MAD \(programming language\)")
* [Magik](</wiki/Magik_\(programming_language\)#Hello_World_example> "Magik \(programming language\)")
* [Malbolge](</wiki/Malbolge#Hello,_World!> "Malbolge")
* [MATLAB](</wiki/MATLAB#"Hello,_world!"_example> "MATLAB")
* [Mercury](</wiki/Mercury_\(programming_language\)#Examples> "Mercury \(programming language\)")
* [MicroPython](</wiki/MicroPython> "MicroPython")
* [Microsoft Small Basic](</wiki/Microsoft_Small_Basic#Language> "Microsoft Small Basic")
* [mIRC scripting language](</wiki/MIRC_scripting_language#Code_examples> "MIRC scripting language")
* [MMIX](</wiki/MMIX#Architecture> "MMIX")
* [Mockito](</wiki/Mockito#Example> "Mockito")
* [Modula-3](</wiki/Modula-3#Syntax> "Modula-3")
* [Mojo](</wiki/Mojo_\(programming_language\)#Programming_examples> "Mojo \(programming language\)")
* [Monad](</wiki/Monad_\(functional_programming\)#IO_monad_\(Haskell\)> "Monad \(functional programming\)")
* [MUMPS](</wiki/MUMPS#Hello,_World!_example> "MUMPS")
* [MXML](</wiki/MXML#Example_source_code> "MXML")
* [Nemerle](</wiki/Nemerle#Hello,_World!> "Nemerle")
* [Newspeak](</wiki/Newspeak_\(programming_language\)#"Hello_World"_example> "Newspeak \(programming language\)")
* [Nim](</wiki/Nim_\(programming_language\)#Hello_world> "Nim \(programming language\)")
* [NWScript](</wiki/NWScript#Hello_world> "NWScript")
* [OmniMark](</wiki/OmniMark#Example_code> "OmniMark")
* [Opa](</wiki/Opa_\(programming_language\)#Hello_world> "Opa \(programming language\)")
* [OpenEdge Advanced Business Language](</wiki/OpenEdge_Advanced_Business_Language#Hello_World> "OpenEdge Advanced Business Language")
* [Open Programming Language](</wiki/Open_Programming_Language#Examples> "Open Programming Language")
* [Oriel](</wiki/Oriel_\(scripting_language\)#Examples> "Oriel \(scripting language\)")
* [ParaSail](</wiki/ParaSail_\(programming_language\)#Examples> "ParaSail \(programming language\)")
* [Parrot assembly language](</wiki/Parrot_assembly_language> "Parrot assembly language")
* [Parrot intermediate representation](</wiki/Parrot_intermediate_representation#Example> "Parrot intermediate representation")
* [Pascal](</wiki/Pascal_\(programming_language\)#Language_constructs> "Pascal \(programming language\)")
* [PCASTL](</wiki/PCASTL#Hello_world> "PCASTL")
* [PDP-8](</wiki/PDP-8#String_output> "PDP-8")
* [Perl](</wiki/Perl_language_structure#Basic_syntax> "Perl language structure")
* [Perl module](</wiki/Perl_module#Examples> "Perl module")
* [PHP](</wiki/PHP#Syntax> "PHP")
* [Plack](</wiki/Plack_\(software\)#Examples> "Plack \(software\)")
* [Plua](</wiki/Plua#Sample_code,_Plua_1> "Plua")
* [Plus](</wiki/Plus_\(programming_language\)#"Hello,_world"_example> "Plus \(programming language\)")
* [PostScript](</wiki/PostScript#"Hello_world"> "PostScript")
* [PowerBASIC](</wiki/PowerBASIC#Hello_world> "PowerBASIC")
* [Prolog](</wiki/Prolog#Hello_World> "Prolog")
* [PureBasic](</wiki/PureBasic#Hello_World_example> "PureBasic")
* [Pure Data](</wiki/Pure_Data#Code_examples> "Pure Data")
* [PureScript](</wiki/PureScript#Examples> "PureScript")
* [PyGTK](</wiki/PyGTK#Syntax> "PyGTK")
* [Python](</wiki/Python_\(programming_language\)#Code_examples> "Python \(programming language\)")
* [Q](</wiki/Q_\(programming_language_from_Kx_Systems\)#Examples> "Q \(programming language from Kx Systems\)")
* [QB64](</wiki/QB64#Syntax> "QB64")
* [QuickBASIC](</wiki/QuickBASIC#Syntax_example> "QuickBASIC")
* [R](</wiki/R_\(programming_language\)#Hello,_World!> "R \(programming language\)")
* [Rack](</wiki/Rack_\(web_server_interface\)#Example_application> "Rack \(web server interface\)")
* [Racket](</wiki/Racket_\(programming_language\)#Code_examples> "Racket \(programming language\)")
* [Raku](</wiki/Raku_\(programming_language\)#Hello_world> "Raku \(programming language\)")
* [React](</wiki/React_\(software\)#Basic_usage> "React \(software\)")
* [React Native](</wiki/React_Native#Hello_World_example> "React Native")
* [Rebol](</wiki/Rebol#Design> "Rebol")
* [Red](</wiki/Red_\(programming_language\)#Hello_World!> "Red \(programming language\)")
* [Refal](</wiki/Refal#Basics> "Refal")
* [RGtk2](</wiki/RGtk2#Syntax> "RGtk2")
* [Ring](</wiki/Ring_\(programming_language\)#Hello_World_program> "Ring \(programming language\)")
* [Robot Framework](</wiki/Robot_Framework#Examples> "Robot Framework")
* [Ruby](</wiki/Ruby_syntax#Interactive_sessions> "Ruby syntax")
* [Rust](</wiki/Rust_\(programming_language\)#Hello_World_program> "Rust \(programming language\)")
* [SAKO](</wiki/SAKO_\(programming_language\)#"Hello,_world"_example> "SAKO \(programming language\)")
* [SARL](</wiki/SARL_\(programming_language\)#Hello,_World!> "SARL \(programming language\)")
* [Scala](</wiki/Scala_\(programming_language\)#"Hello_World"_example> "Scala \(programming language\)")
* [Scilab](</wiki/Scilab#Syntax> "Scilab")
* [Scratch](</wiki/Scratch_\(programming_language\)> "Scratch \(programming language\)")
* [Sed](</wiki/Sed#Hello,_world!_example> "Sed")
* [Self](</wiki/Self_\(programming_language\)#Basic_syntax> "Self \(programming language\)")
* [Shakespeare](</wiki/Shakespeare_Programming_Language#Example_code> "Shakespeare Programming Language")
* [Simula](</wiki/Simula#Classic_Hello_world> "Simula")
* [SmallBASIC](</wiki/SmallBASIC#Syntax> "SmallBASIC")
* [Smalltalk](</wiki/Smalltalk#Hello_World_example> "Smalltalk")
* [Standard ML](</wiki/Standard_ML#Hello,_world!> "Standard ML")
* [Standard Widget Toolkit](</wiki/Standard_Widget_Toolkit#Programming> "Standard Widget Toolkit")
* [Swift](</wiki/Swift_\(programming_language\)#Basic_Syntax> "Swift \(programming language\)")
* [TeX](</wiki/TeX#How_it_is_run> "TeX")
* [TI-990](</wiki/TI-990#Assembly_Language_Programming_Example> "TI-990")
* [TI‑BASIC](</wiki/TI-BASIC#Hello_world> "TI-BASIC")
* [Tornado](</wiki/Tornado_\(web_server\)#Example> "Tornado \(web server\)")
* [Turbo Pascal](</wiki/Turbo_Pascal#Syntax> "Turbo Pascal")
* [Turing](</wiki/Turing_\(programming_language\)#Syntax> "Turing \(programming language\)")
* [UCBLogo](</wiki/UCBLogo#Syntax> "UCBLogo")
* [UEFI](</wiki/UEFI#Applications_development> "UEFI")
* [Umple](</wiki/Umple#Examples> "Umple")
* [Unlambda](</wiki/Unlambda#Basic_principles> "Unlambda")
* [V](</wiki/V_\(programming_language\)#Hello_world> "V \(programming language\)")
* [Vala](</wiki/Vala_\(programming_language\)#Hello_world> "Vala \(programming language\)")
* [Visual Basic](</wiki/Visual_Basic_\(.NET\)#Hello_World!> "Visual Basic \(.NET\)")
* [Visual IRC](</wiki/Visual_IRC#Code_examples> "Visual IRC")
* [web2py](</wiki/Web2py> "Web2py")
* [Web Server Gateway Interface](</wiki/Web_Server_Gateway_Interface#Example_application> "Web Server Gateway Interface")
* [Whitespace](</wiki/Whitespace_\(programming_language\)#Sample_code> "Whitespace \(programming language\)")
* [Wt](</wiki/Wt_\(web_toolkit\)#Code_example> "Wt \(web toolkit\)")
* [XBLite](</wiki/XBLite#Sample_Code> "XBLite")
* [Xojo](</wiki/Xojo#Example_code> "Xojo")
* [Zig](</wiki/Zig_\(programming_language\)#Hello_World> "Zig \(programming language\)")
## See also
[[edit](</w/index.php?title=%22Hello,_World!%22_program&action=edit&section=5> "Edit section: See also")]
* [](</wiki/File:Octicons-terminal.svg>)[Computer programming portal](</wiki/Portal:Computer_programming> "Portal:Computer programming")
* ["99 Bottles of Beer" as used in computer science](</wiki/99_Bottles_of_Beer#References_in_computer_science> "99 Bottles of Beer")
* [Bad Apple!! § Use of video as a graphical and audio test](</wiki/Bad_Apple!!#Use_of_video_as_a_graphical_and_audio_test> "Bad Apple!!") (graphic equivalent to "Hello, World!" for old hardware)
* [Foobar](</wiki/Foobar> "Foobar")
* [Java Pet Store](</wiki/Java_BluePrints> "Java BluePrints")
* [Just another Perl hacker](</wiki/Just_another_Perl_hacker> "Just another Perl hacker")
* [Outline of computer science](</wiki/Outline_of_computer_science> "Outline of computer science")
* [TPK algorithm](</wiki/TPK_algorithm> "TPK algorithm")
* [Coding](</wiki/Computer_programming> "Computer programming")
## References
[[edit](</w/index.php?title=%22Hello,_World!%22_program&action=edit&section=6> "Edit section: References")]
1.
* ^
* Langbridge, James A. (3 December 2013). [_Professional Embedded ARM Development_](<https://books.google.com/books?id=y51NAgAAQBAJ&pg=PA74>). John Wiley & Sons. [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [9781118887820](</wiki/Special:BookSources/9781118887820> "Special:BookSources/9781118887820").
2.
* ^
* [Kernighan, Brian W.](</wiki/Brian_Kernighan> "Brian Kernighan"); [Ritchie, Dennis M.](</wiki/Dennis_Ritchie> "Dennis Ritchie") (1978). [_The C Programming Language_](<https://archive.org/details/cprogramminglang00kern>) (1st ed.). [Englewood Cliffs, New Jersey](</wiki/Englewood_Cliffs,_New_Jersey> "Englewood Cliffs, New Jersey"): [Prentice Hall](</wiki/Prentice_Hall> "Prentice Hall"). p. [6](<https://archive.org/details/cprogramminglang00kern/page/6/mode/2up?q=%22hello%2C+world%22>). [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [0-13-110163-3](</wiki/Special:BookSources/0-13-110163-3> "Special:BookSources/0-13-110163-3").
3.
* ^
* [Kernighan, Brian](</wiki/Brian_Kernighan> "Brian Kernighan") (1974). ["Programming in C: A Tutorial"](<https://www.bell-labs.com/usr/dmr/www/ctut.pdf>) (PDF). Bell Labs. [Archived](<https://web.archive.org/web/20220322215231/https://www.bell-labs.com/usr/dmr/www/ctut.pdf>) (PDF) from the original on 22 March 2022. Retrieved 9 January 2019.
4.
* ^
* Johnson, S. C.; [Kernighan, B. W.](</wiki/Brian_Kernighan> "Brian Kernighan") [_The Programming Language B_](<https://www.bell-labs.com/usr/dmr/www/bintro.html>). Bell Labs. [Archived](<https://web.archive.org/web/20150611114355/https://www.bell-labs.com/usr/dmr/www/bintro.html>) from the original on 11 June 2015. Retrieved 8 August 2024.
5.
* ^
* ["BCPL"](<http://www.catb.org/jargon/html/B/BCPL.html>). _[Jargon File](</wiki/Jargon_File> "Jargon File")_. [Archived](<https://web.archive.org/web/20180403000549/http://www.catb.org/jargon/html/B/BCPL.html>) from the original on 3 April 2018. Retrieved 21 April 2013.
6.
* ^
* ["William B. Williams, Radio Personality, Dies"](<https://select.nytimes.com/search/restricted/article?res=F50714FF3E5B0C778CDDA10894DE484D81>). _The New York Times_. 4 August 1986.
7.
* ^
* ["C++ Programming/Examples/Hello world"](<https://en.wikibooks.org/wiki/C%2B%2B_Programming/Examples/Hello_world>). [Wikibooks](</wiki/Wikibooks> "Wikibooks"). [Archived](<https://web.archive.org/web/20220328130457/https://en.wikibooks.org/wiki/C%2B%2B_Programming/Examples/Hello_world>) from the original on 28 March 2022. Retrieved 16 March 2022.
8.
* ^
* [A Tutorial for the Go Programming Language.](<https://golang.org/doc/go_tutorial.html#tmp_20>) [Archived](<https://web.archive.org/web/20100726052120/http://golang.org/doc/go_tutorial.html#tmp_20>) 26 July 2010 at the [Wayback Machine](</wiki/Wayback_Machine> "Wayback Machine") The Go Programming Language. Retrieved 26 July 2011.
9.
* ^
* Silva, Mike (11 September 2013). ["Introduction to Microcontrollers - Hello World"](<http://www.embeddedrelated.com/showarticle/460.php>). _EmbeddedRelated.com_. [Archived](<https://web.archive.org/web/20150522081938/http://www.embeddedrelated.com/showarticle/460.php>) from the original on 22 May 2015. Retrieved 19 May 2015.
10.
* ^
* George, Ligo (8 May 2013). ["Blinking LED using Atmega32 Microcontroller and Atmel Studio"](<https://electrosome.com/blinking-led-atmega32-avr-microcontroller/>). _electroSome_. [Archived](<https://web.archive.org/web/20141105123532/http://electrosome.com/blinking-led-atmega32-avr-microcontroller>) from the original on 5 November 2014. Retrieved 19 May 2015.
11.
* ^
* PT, Ranjeeth. ["2. AVR Microcontrollers in Linux HOWTO"](<http://www.tldp.org/HOWTO/Avr-Microcontrollers-in-Linux-Howto/x207.html>). _The Linux Documentation Project_. [Archived](<https://web.archive.org/web/20150502194301/http://www.tldp.org/HOWTO/Avr-Microcontrollers-in-Linux-Howto/x207.html>) from the original on 2 May 2015. Retrieved 19 May 2015.
12.
* ^
* Andersson, Sven-Åke (2 April 2012). ["3.2 The first Altera FPGA design"](<https://web.archive.org/web/20150521222132/http://www.rte.se/blog/blogg-modesty-corex/first-altera-fpga-design/3.2>). Raidió Teilifís Éireann. Archived from [the original](<http://www.rte.se/blog/blogg-modesty-corex/first-altera-fpga-design/3.2>) on 21 May 2015. Retrieved 19 May 2015.
13.
* ^
* Fabio, Adam (6 April 2014). ["CPLD Tutorial: Learn programmable logic the easy way"](<http://hackaday.com/2014/04/06/cpld-tutorial-learn-programmable-logic-the-easy-way/>). _Hackaday_. [Archived](<https://web.archive.org/web/20150520063507/http://hackaday.com/2014/04/06/cpld-tutorial-learn-programmable-logic-the-easy-way/>) from the original on 20 May 2015. Retrieved 19 May 2015.
14.
* ^
* ["Hello"](<https://archive.today/20140529011826/http://www.gnu.org/software/hello/>). _GNU Project_. Free Software Foundation. Archived from [the original](<https://www.gnu.org/software/hello/>) on 29 May 2014. Retrieved 7 July 2017.
15.
* ^
* Jolif, Christophe (January 2003). "Bringing SVG Power to Java Applications". _Sun Developer Network_.
16.
* ^
* de Dinechin, Christophe (24 July 2010). ["Hello world!"](<http://grenouillebouillie.wordpress.com/2010/07/24/hello-world/>). Grenouille Bouillie.
17.
* ^
* ["Teaching the Nintendo Generation to Program"](<https://web.archive.org/web/20160505190520/http://www.bfoit.org/itp/Soloway/CACM_Nintendo_Generation.pdf>) (PDF). _bfoit.org_. Archived from [the original](<http://www.bfoit.org/itp/Soloway/CACM_Nintendo_Generation.pdf>) (PDF) on 5 May 2016. Retrieved 27 December 2015.
18.
* ^
* Vries, Joey de (2020). _Learn OpenGL - Graphics Programming_. Kendall & Welling. p. 26. [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-90-90-33256-7](</wiki/Special:BookSources/978-90-90-33256-7> "Special:BookSources/978-90-90-33256-7").
19.
* ^
* Beuken, Brian (January 2018). "Coding games on the Raspberry Pi in C/C++ Part 01". _[The MagPi](</wiki/The_MagPi> "The MagPi")_. No. 65. p. 57. "next time we will expand our code to start working with graphics and the famous 'hello triangle' code that absolutely no one uses except game coders"
20.
* ^
* O'Dwyer, Arthur (September 2017). [_Mastering the C++17 STL: Make full use of the standard library components in C++17_](<https://books.google.com/books?id=zJlGDwAAQBAJ&q=%22TTHW%22&pg=PA251>). [Packt Publishing Ltd](</wiki/Packt_Publishing_Ltd> "Packt Publishing Ltd"). p. 251. [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [978-1-78728-823-2](</wiki/Special:BookSources/978-1-78728-823-2> "Special:BookSources/978-1-78728-823-2"). Retrieved 4 December 2019.
21.
* ^
* Wiegers, Harold (28 June 2018). ["The importance of "Time to First Hello, World!" an efficient API program"](<https://apifriends.com/api-management/api-program-time-first-hello-world/>). [Archived](<https://web.archive.org/web/20200219061813/https://apifriends.com/api-management/api-program-time-first-hello-world/>) from the original on 19 February 2020. Retrieved 19 February 2020.
22.
* ^
* Jin, Brenda; Sahni, Saurabh; Shevat, Amir (29 August 2018). [_Designing Web APIs: Building APIs That Developers Love_](<https://books.google.com/books?id=Dg1rDwAAQBAJ&q=%22time%20to%20hello%20world%22&pg=PT150>). O'Reilly Media. [ISBN](</wiki/ISBN_\(identifier\)> "ISBN \(identifier\)") [9781492026877](</wiki/Special:BookSources/9781492026877> "Special:BookSources/9781492026877"). Retrieved 19 February 2020.
## External links
[[edit](</w/index.php?title=%22Hello,_World!%22_program&action=edit&section=7> "Edit section: External links")]
[](</wiki/File:Commons-logo.svg>)
Wikimedia Commons has media related to [Hello World](<https://commons.wikimedia.org/wiki/Category:Hello_World> "commons:Category:Hello World").
[](</wiki/File:Wikibooks-logo-en-noslogan.svg>)
The Wikibook _[Computer Programming](<https://en.wikibooks.org/wiki/Computer_Programming> "wikibooks:Computer Programming")_ has a page on the topic of: _
* [Hello world](<https://en.wikibooks.org/wiki/Computer_Programming/Hello_world> "wikibooks:Computer Programming/Hello world")
[](</wiki/File:Wikiversity_logo_2017.svg>)
Wikiversity has learning resources about _
* ["Hello, World!" program](<https://en.wikiversity.org/wiki/Special:Search/%22Hello,_World!%22_program> "v:Special:Search/"Hello, World!" program")
* [The Hello World Collection](<https://helloworldcollection.de>)
* ["Hello world/Text"](<https://rosettacode.org/wiki/Hello_world/Text>). _[Rosetta Code](</wiki/Rosetta_Code> "Rosetta Code")_. 23 May 2024.
* ["GitHub – leachim6/hello-world: Hello world in every computer language. Thanks to everyone who contributes to this, make sure to see CONTRIBUTING.md for contribution instructions!"](<https://github.com/leachim6/hello-world>). _[GitHub](</wiki/GitHub> "GitHub")_. 30 October 2021.
* ["Unsung Heroes of IT: Part One: Brian Kernighan"](<https://web.archive.org/web/20160326193543/http://theunsungheroesofit.com/helloworld/>). _TheUnsungHeroesOfIT.com_. Archived from [the original](<http://theunsungheroesofit.com/helloworld/>) on 26 March 2016. Retrieved 23 August 2014.
* [v](</wiki/Template:Standard_test_item> "Template:Standard test item")
* [t](</wiki/Template_talk:Standard_test_item> "Template talk:Standard test item")
* [e](</wiki/Special:EditPage/Template:Standard_test_item> "Special:EditPage/Template:Standard test item")
Standard test items
* [Pangram](</wiki/Pangram> "Pangram")
* [Reference implementation](</wiki/Reference_implementation> "Reference implementation")
* [Sanity check](</wiki/Sanity_check> "Sanity check")
* [Standard test image](</wiki/Standard_test_image> "Standard test image")
[Artificial intelligence](</wiki/Artificial_intelligence> "Artificial intelligence")
([Machine learning](</wiki/Machine_learning> "Machine learning"))|
* [Chinese room](</wiki/Chinese_room> "Chinese room")
* [ImageNet](</wiki/ImageNet> "ImageNet")
* [MNIST database](</wiki/MNIST_database> "MNIST database")
* [Turing test](</wiki/Turing_test> "Turing test")
* [List](</wiki/List_of_datasets_for_machine-learning_research> "List of datasets for machine-learning research")
Television ([test card](</wiki/Test_card> "Test card"))|
* [SMPTE color bars](</wiki/SMPTE_color_bars> "SMPTE color bars")
* [EBU colour bars](</wiki/EBU_colour_bars> "EBU colour bars")
* [Indian-head test pattern](</wiki/Indian-head_test_pattern> "Indian-head test pattern")
* [EIA 1956 resolution chart](</wiki/EIA_1956_resolution_chart> "EIA 1956 resolution chart")
* [BBC Test Card](</wiki/List_of_BBC_test_cards> "List of BBC test cards") [A](</wiki/List_of_BBC_test_cards#Test_Card_A> "List of BBC test cards"), [B](</wiki/List_of_BBC_test_cards#Test_Card_B> "List of BBC test cards"), [C](</wiki/List_of_BBC_test_cards#Test_Card_C> "List of BBC test cards"), [D](</wiki/List_of_BBC_test_cards#Test_Card_D> "List of BBC test cards"), [E](</wiki/List_of_BBC_test_cards#Test_Card_E_\(later_Test_Card_C\)> "List of BBC test cards"), [F](</wiki/Test_Card_F> "Test Card F"), [G](</wiki/List_of_BBC_test_cards#Test_Card_G> "List of BBC test cards"), [H](</wiki/List_of_BBC_test_cards#Test_Card_H> "List of BBC test cards"), [J](</wiki/Test_Card_F#testcardj> "Test Card F"), [W](</wiki/Test_Card_F#testcardw> "Test Card F"), [X](</wiki/Test_Card_F#testcardx> "Test Card F")
* [ETP-1](</wiki/ETP-1> "ETP-1")
* [Philips circle pattern](</wiki/Philips_circle_pattern> "Philips circle pattern") ([PM 5538](</wiki/Philips_circle_pattern#PM5534> "Philips circle pattern"), [PM 5540](</wiki/Philips_PM5540> "Philips PM5540"), [PM 5544](</wiki/Philips_circle_pattern#PM5544> "Philips circle pattern"), [PM 5644](</wiki/Philips_circle_pattern#PM5644> "Philips circle pattern"))
* [Snell & Wilcox SW2/SW4](</wiki/Snell_%26_Wilcox_Zone_Plate> "Snell & Wilcox Zone Plate")
* [Telefunken FuBK](</wiki/Telefunken_FuBK> "Telefunken FuBK")
* [TVE test card](</wiki/TVE_test_card> "TVE test card")
* [UEIT](</wiki/Universal_Electronic_Test_Chart> "Universal Electronic Test Chart")
[Computer languages](</wiki/Computer_language> "Computer language")|
* "Hello, World!" program
* [Quine](</wiki/Quine_\(computing\)> "Quine \(computing\)")
* [Trabb Pardo–Knuth algorithm](</wiki/TPK_algorithm> "TPK algorithm")
* [Man or boy test](</wiki/Man_or_boy_test> "Man or boy test")
* [Just another Perl hacker](</wiki/Perl#Community> "Perl")
[Data compression](</wiki/Data_compression> "Data compression")|
* [Calgary corpus](</wiki/Calgary_corpus> "Calgary corpus")
* [Canterbury corpus](</wiki/Canterbury_corpus> "Canterbury corpus")
* [Silesia corpus](</wiki/Silesia_corpus> "Silesia corpus")
* [enwik8, enwik9](</wiki/Hutter_Prize> "Hutter Prize")
[3D computer graphics](</wiki/3D_computer_graphics> "3D computer graphics")|
* [3DBenchy](</wiki/3DBenchy> "3DBenchy")
* [Cornell box](</wiki/Cornell_box> "Cornell box")
* [Stanford bunny](</wiki/Stanford_bunny> "Stanford bunny")
* [Stanford dragon](</wiki/Stanford_dragon> "Stanford dragon")
* [Utah teapot](</wiki/Utah_teapot> "Utah teapot")
* [List](</wiki/List_of_common_3D_test_models> "List of common 3D test models")
[2D computer graphics](</wiki/2D_computer_graphics> "2D computer graphics")|
* [Ghostscript tiger](</wiki/File:Ghostscript_Tiger.svg> "File:Ghostscript Tiger.svg")
* [Lena](</wiki/Lenna> "Lenna")
[Typography](</wiki/Typography> "Typography") ([filler text](</wiki/Filler_text> "Filler text"))|
* [Etaoin shrdlu](</wiki/Etaoin_shrdlu> "Etaoin shrdlu")
* [Hamburgevons](</wiki/Hamburgevons> "Hamburgevons")
* [Lorem ipsum](</wiki/Lorem_ipsum> "Lorem ipsum")
* [The quick brown fox jumps over the lazy dog](</wiki/The_quick_brown_fox_jumps_over_the_lazy_dog> "The quick brown fox jumps over the lazy dog")
Other|
* Acid
* [1](</wiki/Acid1> "Acid1")
* [2](</wiki/Acid2> "Acid2")
* [3](</wiki/Acid3> "Acid3")
* ["Bad Apple!!"](</wiki/Bad_Apple!!#Use_of_video_as_a_graphical_and_audio_test> "Bad Apple!!")
* [EICAR test file](</wiki/EICAR_test_file> "EICAR test file")
* [Functions for optimization](</wiki/Test_functions_for_optimization> "Test functions for optimization")
* [GTUBE](</wiki/GTUBE> "GTUBE")
* [Harvard sentences](</wiki/Harvard_sentences> "Harvard sentences")
* ["The North Wind and the Sun"](</wiki/The_North_Wind_and_the_Sun#Use_in_phonetic_demonstrations> "The North Wind and the Sun")
* ["Tom's Diner"](</wiki/Tom%27s_Diner#The_"Mother_of_the_MP3"> "Tom's Diner")
* [SMPTE universal leader](</wiki/Film_leader> "Film leader")
* [EURion constellation](</wiki/EURion_constellation> "EURion constellation")
* [Webdriver Torso](</wiki/Webdriver_Torso> "Webdriver Torso")
* [1951 USAF resolution test chart](</wiki/1951_USAF_resolution_test_chart> "1951 USAF resolution test chart")
Retrieved from "[https://en.wikipedia.org/w/index.php?title=%22Hello,_World!%22_program&oldid=1305809741](<https://en.wikipedia.org/w/index.php?title=%22Hello,_World!%22_program&oldid=1305809741>)"
[Categories](</wiki/Help:Category> "Help:Category"):
* [Test items in computer languages](</wiki/Category:Test_items_in_computer_languages> "Category:Test items in computer languages")
* [Computer programming folklore](</wiki/Category:Computer_programming_folklore> "Category:Computer programming folklore")
Hidden categories:
* [Webarchive template wayback links](</wiki/Category:Webarchive_template_wayback_links> "Category:Webarchive template wayback links")
* [Articles with short description](</wiki/Category:Articles_with_short_description> "Category:Articles with short description")
* [Short description is different from Wikidata](</wiki/Category:Short_description_is_different_from_Wikidata> "Category:Short description is different from Wikidata")
* [Use dmy dates from March 2022](</wiki/Category:Use_dmy_dates_from_March_2022> "Category:Use dmy dates from March 2022")
* [Commons category link from Wikidata](</wiki/Category:Commons_category_link_from_Wikidata> "Category:Commons category link from Wikidata")
* [Articles with example code](</wiki/Category:Articles_with_example_code> "Category:Articles with example code")
* [Articles with quotation marks in the title](</wiki/Category:Articles_with_quotation_marks_in_the_title> "Category:Articles with quotation marks in the title")
*[v]: View this template
*[t]: Discuss this template
*[e]: Edit this template

---
*Document traité automatiquement par le système de recherche agentique*
