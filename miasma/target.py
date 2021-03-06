import os,platform
from array import array
from miasma.miasmadefs import *
from miasma.patchreader import * 
from miasma.globals import *
from ctypes import *

class user_regs_struct(Structure):
     _fields_ = [
         ('ebx',c_ulong),
         ('ecx',c_ulong),
         ('edx',c_ulong),
         ('esi',c_ulong),
         ('edi',c_ulong),
         ('ebp',c_ulong),
         ('eax',c_ulong),
         ('xds',c_ulong),
         ('xes',c_ulong),
         ('xfs',c_ulong),
         ('xgs',c_ulong),
         ('orig_eax',c_ulong),
         ('eip',c_ulong),
         ('xcs',c_ulong),
         ('eflags',c_ulong),
         ('esp',c_ulong),
         ('xss',c_ulong),
         ]

class Target(object):
	def __init__(self,path,args):
		self.path = path
		self.args = args
		if(os.name != 'nt'):
			self.libc = CDLL('libc.so.6')
			if(platform.machine() == 'x86_64'):
				print("64 bit OS Detected")
				self.libc = CDLL('/usr/lib32/libc.so.6')
				
			self.child = self.libc.fork()
		else:
			self.kernel32 = windll.kernel32
			self.child = kernel32.CreateProcessA("%s %s" %(self.path,args),
									None,
									None,
									None,
									None,
									creation_flags,
									None,
									None,
									byref(startupinfo),
									byref(process_information))
		(base,bin) = os.path.split(path)
		os.chdir(base)
		self.mods = ""
	def run(self):
		if(self.child == 0):
			self.libc.ptrace(PTRACE_TRACEME,0,None,None)
			self.libc.execl(self.path,self.path,self.args,None)
		else:
			self.mods = Patchreader("%s.msa" % self.path)
			self.libc.wait(None)
			self.init_mods()
			
			#self.libc.ptrace(PTRACE_POKEDATA,self.child,0xA7ED5A0,640)
			
			self.libc.ptrace(PTRACE_CONT,self.child,None,None)
			if(DEBUG):
				print("DEBUG: Binary Executed!")

			#status = 0
			#regs = user_regs_struct()
			#self.libc.wait(None)
			#self.libc.ptrace(PTRACE_GETREGSET,self.child,None, byref(regs))
			#print("EIP: %04X" % regs.eip)
			#if(status != 0):
			#self.libc.ptrace(PTRACE_POKEDATA,self.child,0x8070EB1,0xCC)
			#self.libc.ptrace(PTRACE_POKEDATA,self.child,0xA7ED5A0,320)
			#self.libc.ptrace(PTRACE_POKEDATA,self.child,0xA7ED5A4,240)
			#print(self.libc.ptrace(PTRACE_PEEKDATA,self.child,0xA7ED5A0,None))
			
			#print("0x%0x,0x%0x,0x%0x,0x%0x" % (regs.contents.eax,regs.contents.ebx,regs.contents.ecx,regs.contents.edx))
			#self.libc.ptrace(PTRACE_POKEDATA,self.child,0x8070EB1,0xFDADB6E8)
			#self.libc.ptrace(PTRACE_CONT,self.child,None,None)	
					
			#self.libc.ptrace(PTRACE_SETOPTIONS, self.child,None,PTRACE_O_TRACEEXIT);
			

	
	def readMem(self,offset):
		data = self.libc.ptrace(PTRACE_PEEKDATA,self.child,ELF_BASE+offset,None)
		return data
	
	def writeMem(self,offset,data):
		#print("DEBUG: WriteMem: %04X : %04X" % (offset, data))
		self.libc.ptrace(PTRACE_POKEDATA,self.child,ELF_BASE+offset,data)
	
	def dump_binary(self):
		outfile = open("outbin","wb")
		offset = 0
		while(1):
			val = self.readMem(offset) & 0xFFFFFFFF
			outfile.write(struct.pack("<I",val))
			offset +=4
	
	def init_mods(self):
		for offset in sorted(self.mods.mem_mods.iterkeys()):
			#Loading Logic
			
			bytes = array('B', self.mods.mem_mods[offset][1])
			if(len(self.mods.mem_mods[offset][1]) == 4):
				val = struct.unpack('<I', bytes)[0]
				data = 0
				if(val <= 0xFF):
					data = self.readMem(offset) & 0xFFFFFF00
				elif(val <= 0xFFFF):
					data = self.readMem(offset) & 0xFFFF0000
				elif(val <= 0xFFFFFF):
					data = self.readMem(offset) & 0xFF000000							
				
				data+=val
				self.writeMem(offset,data)
			else:

				blocksize = 4
				count = len(self.mods.mem_mods[offset][1])
				curr_offset = offset
				while(count):
					#I'm so ashamed...
					if(count < 4):
						finval = 0
						blocksize = count
						#We know there will at least be SOME overflow...
						data = bytearray(struct.pack("<I",self.readMem(curr_offset) & 0xFFFFFFFF))
						#print(curr_offset)
						#print(blocksize)
						for i in range(0,blocksize):
							finval = finval << 8
							finval += bytes[i]
						
						for i in range(blocksize,4):
							finval = finval << 8
							finval += data[i]
						
						#Final Endian Swap
						finval = struct.unpack("<I",struct.pack(">I",finval))[0]
						#print("%04X" % finval)
						self.writeMem(curr_offset,finval)		
						
					else:
						blocksize = 4
						data = struct.unpack('<I',bytes[:blocksize])[0]

						self.writeMem(curr_offset,data)
					
					bytes = bytes[blocksize:]
					count -= blocksize
					curr_offset += blocksize
					
				
			if(DEBUG):
				print("DEBUG: Loaded %s" % self.mods.mem_mods[offset][0])
			else:
				pass
		if(DEBUG):
			print("DEBUG: Binary Prepatching Completed!")
		#self.dump_binary()# Debugging
