class Node:
    def __init__(self,data):
        self.data = data
        self.next = None

node1 = Node(-1)
node2 = Node(5)
node3 = Node(7)
node4 = Node(0)

node1.next = node2
node2.next = node3
node3.next = node4

# currentNode = node1

# # while currentNode:
# #     print(currentNode.data,end='->')
# #     currentNode = currentNode.next
# # print("null") 



# while currentNode:
#     print(currentNode.data,end="->")
#     currentNode = currentNode.next

# print("null")

# class Node:
#     def __init__(self, data):
#         self.data = data
#         self.next = None
#         self.prev = None

# node1 = Node(3)
# node2 = Node(5)
# node3 = Node(13)
# node4 = Node(2)

# node1.next = node2
# node1.prev = node4

# node2.prev = node1
# node2.next = node3

# node3.prev = node2
# node3.next = node4

# node4.prev = node3
# node4.next = node1

# print("\nTraversing forward:")
# currentNode = node1
# startNode = node1
# print(currentNode.data, end=" -> ")
# currentNode = currentNode.next

# while currentNode != startNode:
#     print(currentNode.data, end=" -> ")
#     currentNode = currentNode.next
# print("...")

# print("\nTraversing backward:")
# currentNode = node4
# startNode = node4
# print(currentNode.data, end=" -> ")
# currentNode = currentNode.prev

# while currentNode != startNode:
#     print(currentNode.data, end=" -> ")
#     currentNode = currentNode.prev
# print("...")

def traversenode(head):
    currentNode = head
    while currentNode:
       print(currentNode.data, end="->")
       currentNode = currentNode.next
    print('Null')


traversenode(node1)

def FindaLowestValue(head):
    minvalue = head.data
    currentNode = head.next
    while currentNode:
       if  currentNode.data < minvalue:
          minvalue = currentNode.data
       currentNode = currentNode.next
    return minvalue

# print(FindaLowestValue(node1))

def findandDelete(head,value):
    currentNode = head.next
    prevNode = head
    if head.data == value:
        return head.next
    while currentNode:
        if currentNode.data == value:
            prevNode.next = currentNode.next
        prevNode = currentNode
        currentNode = currentNode.next
    return head

newNode = findandDelete(node1,-1)        

traversenode(newNode)