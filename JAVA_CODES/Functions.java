import java.util.*;


public class Functions {



   public static void printFactorial(int no) {
       //loop
       if(no < 0) {
           System.out.println("Invalid Number");
           return;//here its good to have a return so wont be needed to run rest of the code.
       }
       int factorial = 1;// not intialised with 0 as anything multiplied with 0 is 0.


       for(int i=no; i>=1; i--) {
           factorial = factorial * i;
       }


       System.out.println(factorial);
       return;//void mein return type is optional but prefer not to put it
   }
   public static void main(String args[]) {
       Scanner sc = new Scanner(System.in);
       int no = sc.nextInt();


       printFactorial(no);
   }
}



