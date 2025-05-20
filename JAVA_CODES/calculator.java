import java.util.*;
public class calculator {
//This is a code for CALCULATOR
    public static void main(String[] args) {
       Scanner sc = new Scanner(System.in);
       int RESULT=0;
       System.out.print("\tCALCULATOR\t\n");
       System.out.println("Enter first number: ");
       int no1=sc.nextInt();
       System.out.println("Enter second number: ");
       int no2=sc.nextInt();
       System.out.println("Enter the operation you wish to perform:  + , - , * , / \n");
      
    
    System.out.println("Enter 1 for +");
    System.out.println("Enter 2 for +");
    System.out.println("Enter 3 for +");
    System.out.println("Enter 4 for +");
    int choice=sc.nextInt();

         switch (choice) {
            case 1 :
               RESULT=no1+no2;              
                break;
            case 2 :
                RESULT=no1-no2;              
                break;
            case 3 :
                RESULT=no1*no2;              
                break;
            case 4 :
                RESULT=no1/no2;              
                break;            
         
            default:
            System.out.print("INVALID CHOICE");
                break;
         }
         System.out.println("The result is "+ RESULT);
         //notice the use of concatenation operator without this we cant join a string and a variable.
         System.out.println(".......THANK YOU FOR USING.......");
         sc.close();
}
}